#!/usr/bin/env python
from __future__ import print_function
import ast, re, xdis
from xasm.misc import get_opcode
from xdis.opcodes.base import cmp_op

# import xdis.bytecode as Mbytecode

class Instruction(): # (Mbytecode.Instruction):
    def __repr__(self):
        s = ''
        if self.line_no:
            s = "%4d: " % self.line_no
        else:
            s = " " * 6
        s += "%-15s" % self.opname
        if self.arg is not None:
            s += "\t%s" % self.arg
        return s
    pass

def is_int(s):
    try:
        int(s)
        return True
    except:
        return False

def is_lineno(s):
    return re.match('^\d+:', s)

def get_opname_operand(fields):
    assert len(fields) > 0
    if len(fields) > 1:
        if is_int(fields[1]):
            operand = int(fields[1])
        else:
            operand = fields[1]

        return fields[0], operand
    else:
        return fields[0], None

class Assembler(object):
    def __init__(self, python_version):
        self.opc, self.Code = get_opcode(python_version)
        self.code_list = []
        self.codes = []   # FIXME use a better name
        self.status = 'unfinished'
        self.python_version = python_version
        self.timestamp = 0
        self.backpatch = []  # list of backpatch dicts, one for each function
        self.label = []      # list of label dists, one for each function
        self.code = None

    def code_init(self, python_version=None):

        if self.python_version is None and python_version:
            self.python_version = python_version

        self.code = self.Code(
            co_argcount=0,
            co_kwonlyargcount=0,
            co_nlocals=0,
            co_stacksize=10,
            co_flags=0,
            co_code=[],
            co_consts=[],
            co_names=[],
            co_varnames=[],
            co_filename = 'unknown',
            co_name = 'unknown',
            co_firstlineno=1,
            co_lnotab = {},
            co_freevars = [],
            co_cellvars = [])

        self.code.instructions = []

    def update_lists(self, co, label, backpatch):
        self.code_list.append(co)
        self.codes.append(self.code)
        self.label.append(label)
        self.backpatch.append(backpatch)

    def print_instructions(self):
        for inst in self.code.instructions:
            if inst.line_no:
                print()
            print(inst)

    def err(self, mess):
        print(mess)
        self.status = 'errored'

def asm_file(path):
    offset = 0
    methods = {}
    method_name = None
    asm = None
    backpatch_inst = set([])
    label = {}

    lines = open(path).readlines()
    i = 0
    bytecode_seen = False
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith('#'):
            if line.startswith('# Python bytecode '):
                python_version = line[len('# Python bytecode '):].strip().split()[0]
                asm = Assembler(python_version)
                asm.code_init()
                bytecode_seen = True
            elif line.startswith('# Timestamp in code: '):
                text = line[len('# Timestamp in code: '):].strip()
                time_str = text.split()[0]
                if is_int(time_str):
                    asm.timestamp = int(time_str)
            elif line.startswith('# Method Name: '):
                if method_name:
                    co = create_code(asm, label, backpatch_inst)
                    asm.update_lists(co, label, backpatch_inst)
                    label = {}
                    backpatch_inst = set([])
                    methods[method_name] = co
                    offset = 0
                asm.code_init()
                asm.code.co_name = line[len('# Method Name: '):].strip()
                method_name = asm.code.co_name

            elif line.startswith('# Filename: '):
                asm.code.co_filename = line[len('# Filename: '):].strip()
            elif line.startswith('# First Line: '):
                s = line[len('# First Line: '):].strip()
                first_lineno = int(s)
                asm.code.co_firstlineno = first_lineno
            elif line.startswith('# Argument count: '):
                argc = line[len('# Argument count: '):].strip().split()[0]
                asm.code.co_argcount = ast.literal_eval(argc)
            elif line.startswith('# Number of locals: '):
                l_str = line[len('# Number of locals: '):].strip()
                asm.code.co_nlocals = int(l_str)
            elif line.startswith("# Source code size mod 2**32: "):
                l_str = line[len("# Source code size mod 2**32: "):-len(' bytes')].strip()
                asm.size = int(l_str)
            elif line.startswith('# Stack size: '):
                l_str = line[len('# Stack size: '):].strip()
                asm.code.co_stacksize = int(l_str)
            elif line.startswith('# Flags: '):
                flags = line[len('# Flags: '):].strip().split()[0]
                asm.code.co_flags = ast.literal_eval(flags)
            elif line.startswith('# Constants:'):
                count = 0
                while i < len(lines):
                    line = lines[i]
                    i += 1
                    match = re.match('^#\s+(\d+): (.+)$', line)
                    if match:
                        index = int(match.group(1))
                        assert index == count
                        expr = match.group(2)
                        match = re.match('<code object (\S+) at', expr)
                        if match:
                            name = match.group(1)
                            asm.code.co_consts.append(methods[name])
                        else:
                            asm.code.co_consts.append(ast.literal_eval(expr))
                        count += 1
                    else:
                        i -= 1
                        break
                    pass
                pass
            elif line.startswith('# Cell variables:'):
                i = update_code_tuple_field('co_cellvars', asm.code,
                                            lines, i)
            elif line.startswith('# Free variables:'):
                i = update_code_tuple_field('co_freevars', asm.code,
                                            lines, i)
            elif line.startswith('# Names:'):
                i = update_code_tuple_field('co_names', asm.code,
                                            lines, i)
            elif line.startswith('# Varnames:'):
                line = lines[i]
                asm.code.co_varnames = line[1:].strip().split(', ')
                i += 1
        else:
            if not line.strip():
                continue

            match = re.match('^([^\s]+):$', line)
            if match:
                label[match.group(1)] = offset
                continue

            match = re.match('^\s*([\d]+):\s*$', line)
            if match:
                line_no = int(match.group(1))
                asm.code.co_lnotab[offset] = line_no
                continue

            # Opcode section
            assert bytecode_seen, 'File needs to start out with: # Python bytecode <version>'
            fields = line.strip().split()
            line_no = None
            l = len(fields)

            if l > 1:
                if fields[0] == '>>':
                    fields = fields[1:]
                    l -= 1
                if is_lineno(fields[0]) and is_int(fields[1]):
                    line_no = int(fields[0][:-1])
                    opname, operand = get_opname_operand(fields[2:])
                elif is_lineno(fields[0]):
                    line_no = int(fields[0][:-1])
                    fields = fields[1:]
                    if fields[0] == '>>':
                        fields = fields[1:]
                        if is_int(fields[0]):
                            fields = fields[1:]
                    opname, operand = get_opname_operand(fields)
                elif is_int(fields[0]):
                    opname, operand = get_opname_operand(fields[1:])
                else:
                    opname, operand = get_opname_operand(fields)
            else:
                opname, _ = get_opname_operand(fields)

            if opname in asm.opc.opname:
                inst = Instruction()
                inst.opname = opname.replace('+', '_')
                inst.opcode = asm.opc.opmap[inst.opname]
                if xdis.op_has_argument(inst.opcode, asm.opc):
                    inst.arg = operand
                else:
                    inst.arg = None
                inst.line_no = line_no
                asm.code.instructions.append(inst)
                if inst.opcode in asm.opc.JUMP_OPS:
                    if not is_int(operand):
                        backpatch_inst.add(inst)
                offset += xdis.op_size(inst.opcode, asm.opc)
            else:
                raise RuntimeError("Illegal opname %s in: %s" %
                                   (opname, line))
            pass
        pass
    # print(asm.code.co_lnotab)
    if asm:
        co = create_code(asm, label, backpatch_inst)
        asm.update_lists(co, label, backpatch_inst)
    asm.code_list.reverse()
    asm.status = 'finished'
    return asm

def member(l, match_value):
    for i, v in enumerate(l):
        if v == match_value and type(v) == type(match_value):
            return i
        pass
    return -1

def update_code_field(field_name, value, inst, opc):
    l = getattr(opc, field_name)
    # Can't use "in" because True == 1 and False == 0
    # if value in l:
    i = member(l, value)
    if i >= 0:
        inst.arg = i
    else:
        inst.arg = len(l)
        l.append(value)

def update_code_tuple_field(field_name, code, lines, i):
    count = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        match = re.match('^#\s+(\d+): (.+)$', line)
        if match:
            index = int(match.group(1))
            assert index == count
            l = getattr(code, field_name)
            l.append(match.group(2))
            count += 1
        else:
            i -= 1
            break
        pass
    pass
    return i

def err(msg, inst, i):
    msg += ('. Instruction %d:\n%s' % (i, inst))
    raise RuntimeError(msg)

def create_code(asm, label, backpatch):
    # print('label: ', asm.label)
    # print('backpatch: ', asm.backpatch_inst)

    bcode = []
    # print(asm.code.instructions)

    offset = 0
    extended_value = 0
    offset2label = {label[j]:j for j in label}

    for i, inst in enumerate(asm.code.instructions):
        bcode.append(inst.opcode)
        if offset in offset2label:
            if is_int(offset2label[offset]):
                inst.line_no = int(offset2label[offset])
                asm.code.co_lnotab[offset] = inst.line_no

        inst.offset = offset
        offset += xdis.op_size(inst.opcode, asm.opc)

        if xdis.op_has_argument(inst.opcode, asm.opc):
            if inst in backpatch:
                target = inst.arg
                try:
                    if inst.opcode in asm.opc.JREL_OPS:
                        inst.arg = label[target] - offset
                    else:
                        inst.arg = label[target]
                        pass
                    pass
                except KeyError:
                    err("Label %s not found" %  target, inst, i)
            elif is_int(inst.arg):
                if inst.opcode == asm.opc.EXTENDED_ARG:
                    extended_value += inst.arg
                    if asm.opc.version >= 3.6:
                        extended_value <<= 8
                    else:
                        extended_value <<= 16
                pass
            elif inst.arg.startswith('(') and inst.arg.endswith(')'):
                operand = inst.arg[1:-1]
                if inst.opcode in asm.opc.COMPARE_OPS:
                    if operand in cmp_op:
                        inst.arg = cmp_op.index(operand)
                    else:
                        err("Can't handle compare operand %s" % inst.arg, inst, i)

                    pass
                elif inst.opcode in asm.opc.CONST_OPS:
                    operand = ast.literal_eval(operand)
                    update_code_field('co_consts', operand, inst, asm.code)
                elif inst.opcode in asm.opc.LOCAL_OPS:
                    update_code_field('co_varnames', operand, inst, asm.code)
                elif inst.opcode in asm.opc.NAME_OPS:
                    update_code_field('co_names', operand, inst, asm.code)
                elif inst.opcode in asm.opc.FREE_OPS:
                    if operand in asm.code.co_cellvars:
                        inst.arg = asm.code.co_cellvars.index(operand)
                    else:
                        update_code_field('co_freevars', operand, inst, asm.code)
                else:
                    # from trepan.api import debug; debug()
                    err("Can't handle operand %s" % inst.arg, inst, i)
            else:
                # from trepan.api import debug; debug()
                err("Don't understand operand %s expecting int or (..)" % inst.arg, inst, i)

            if asm.opc.version < 3.6:
                if inst.opcode == asm.opc.EXTENDED_ARG:
                    arg_tup = xdis.util.num2code(inst.arg)
                else:
                    arg_tup = xdis.util.num2code(inst.arg - extended_value)
                    extended_value = 0
                bcode += arg_tup
            # 3.6
            else:
                if inst.opcode == asm.opc.EXTENDED_ARG:
                    bcode.append(inst.arg)
                else:
                    bcode.append(inst.arg - extended_value)
                    extended_value = 0
        elif asm.opc.version >= 3.6:
            bcode.append(0)

    if asm.opc.version >= 3.0:
        co_code = bytearray()
        for j in bcode:
            co_code.append(j)
        asm.code.co_code = bytes(co_code)
    else:
        asm.code.co_code = ''.join([chr(j) for j in bcode])

    # Stamp might be added here
    code = asm.code.freeze()
    # asm.print_instructions()

    # print (*args)
    # co = self.Code(*args)
    return code

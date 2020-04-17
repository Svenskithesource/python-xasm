<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Get latest sources:](#get-latest-sources)
- [Change version in xasm/version.py.](#change-version-in-xasmversionpy)
- [Update ChangeLog:](#update-changelog)
- [Update NEWS from ChangeLog. Then:](#update-news-from-changelog-then)
- [Make sure pyenv is running and check newer versions](#make-sure-pyenv-is-running-and-check-newer-versions)
- [Update NEWS from master branch](#update-news-from-master-branch)
- [Check against all versions](#check-against-all-versions)
- [Make packages and tag](#make-packages-and-tag)
- [Upload single package and look at Rst Formating](#upload-single-package-and-look-at-rst-formating)
- [Upload rest of versions](#upload-rest-of-versions)
- [Push tags:](#push-tags)
- [Check on a VM](#check-on-a-vm)

<!-- markdown-toc end -->

# Get latest sources:

    $ git pull

# Change version in xasm/version.py.

    $ emacs xasm/version.py
    $ source xasm/version.py
    $ echo $VERSION
    $ git commit -m"Get ready for release $VERSION" .


# Update ChangeLog:

    $ make ChangeLog

#  Update NEWS from ChangeLog. Then:

    $ emacs NEWS.md
    $ make check
    $ git commit --amend .
    $ git push   # get CI testing going early

# Make sure pyenv is running and check newer versions

    $ pyenv local && source admin-tools/check-versions.sh

# Update NEWS from master branch

    $ git commit -m"Get ready for release $VERSION" .

# Check against all versions

    $ bash && echo $SHLVL # Go into a subshell to protect exit
    $ source admin-tools/check-versions.sh
    $ echo $SHLVL ; exit

# Make packages and tag

    $ make dist

Goto https://github.com/rocky/python-xasm/releases


# Upload single package and look at Rst Formating

	$ twine check dist/xasm-${VERSION}*
    $ twine upload dist/xasm-${VERSION}-py3.3.egg

Check on https://pypi.org/project/xasm/

# Upload rest of versions

    $ twine upload dist/xasm-${VERSION}*

# Push tags:

    $ git push --tags

# Check on a VM

    $ cd /virtual/vagrant/virtual/vagrant/ubuntu-zesty
	$ vagrant up
	$ vagrant ssh
	$ pyenv local 3.5.2
	$ pip install --upgrade xasm
	$ exit
	$ vagrant halt

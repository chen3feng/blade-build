# Installation

By executing the install script, blade can be installed under ~/bin. Currently, because it is still in the development stage, the change is still relatively fast.
It is installed in a soft chain mode. After installation, the original directory that is checked out cannot be deleted.
Currently, blade generates the scons script, so you need to install scons 2.0 or later. If you use ninja as the backend, you need to install ninja.
Blade requires Python 2.7.x and does not support python3 at this time.

Install makes it possible to execute directly in any directory

```bash
$ blade
```

command.
If not, make sure ~/bin is in your PATH environment variable, otherwise modify ~/.profile and add

```bash
export PATH=~/bin:$PATH
```

Then log back in.

# Installation #

By executing the install script, blade can be installed under ~/bin.
It is installed in a soft chain mode. After installation, the original directory that is checked out cannot be deleted.
Blade uses ninja as the backend, you need to install ninja.
Blade supports both Python 2.7.x and Python 3，and Python 2.7 support will be deprecated in the future.

Install makes it possible to execute directly in any directory

```bash
$ blade
usage: blade [-h] [--version] {build,run,test,clean,query,dump} ...
blade: error: too few arguments
Blade(error): Failure
```

If not, make sure ~/bin is in your PATH environment variable, otherwise modify ~/.profile and add

```bash
export PATH=~/bin:$PATH
```

Then relogin.

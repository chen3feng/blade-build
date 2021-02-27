# Accessibility

## Auxiliary Commands

### install

The symbolic link to the blade command will be installed under the ~/bin command.

### lsrc

Lists the source files specified in the current directory and outputs them in the srcs list format of the blade.

### genlibbuild

Automatically generate cc_library with the directory name of the library to test the file name cc_test, proto BUILD file, and assume that these tests depend on this library

### alt

Jump back and forth between the source code directory and the corresponding build results directory

## vim integration

We have written the gram file of vim, highlighting the blade keyword, and it will take effect automatically after installation.

We wrote a custome `Build` command so that we can execute blade directly in vim and quickly jump to the error line (thanks to vim
[QuickFix](https://vimhelp.org/quickfix.txt.html) Features).

When used directly in the vim ':' mode input (with parameters)

```vim
:Build blade build
```

You can build it.

The source code for this command is [here](https://github.com/chen3feng/devenv/blob/master/_vimrc).

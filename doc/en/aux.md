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

We wrote the Blade command so that we can execute the blade directly in vim and quickly jump to the error line (thanks to vim
[hquickfix](ttp://easwy.com/blog/archives/advanced-vim-skills-quickfix-mode/) Features).

When used directly in the vim ':' mode input (with parameters)

```vim
:Blade
```

You can build it.

The source code for this command is [here](https://github.com/chen3feng/tools/blob/master/vimrc).

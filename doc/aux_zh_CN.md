辅助命令
------------
### install
blade命令的符号链接会被安装下面的命令到~/bin 下。

### lsrc
列出当前目录下指定的源文件，以blade的srcs列表格式输出。

### genlibbuild
自动生成以目录名为库名的cc_library，以测试文件的名为名的cc_test，proto的BUILD文件，并假设这些测试都依赖这个库

### vim集成
我们编写了vim的blade语法文件，高亮显示blade关键字，install后就会自动生效。

我们编写了 Blade 命令，使得可以在 vim 中直接执行 blade，并快速跳转到出错行（得益于 vim 的 [hquickfix](ttp://easwy.com/blog/archives/advanced-vim-skills-quickfix-mode/) 特性）。

使用时直接在 vim 的 : 模式输入（可带参数）

```vim
:Blade
```

即可构建。

这个命令的源代码在 tools/.vimrc 中。

### alt
在源代码目录和构建目标目录之间跳转


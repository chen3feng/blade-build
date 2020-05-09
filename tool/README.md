一些可能有用的工具

- bladefunctions
实现了一些命令行中可以调用的辅助shell函数，比如切换代码目录和生成目录。

- fix-include-path.sh
自动修正c/c++文件中#include不带路径，改为带路径的写法。

- genlibbuild
假设当前目录是一个C/C++库，那么自动生成库的BUILD文件，库名为目录名，如果有test文件，自动生成相应的cc_test测试

- lsnobuild
列出那些目录下有Makefile而没有BUILD文件，用于协助采用递归Make的项目迁移到Blade。

- lsrc
按srcs = 需要的格式列出当前目录下所有的C/C++源文件（不包含测试源文件例如*_test.cc）

- merge-static-libs
把一个blade库及其它直接和间接依赖的所有其他库打包成一个大的静态库

- setup-shared-ccache.py
设置单机多个用户之间共用 ccache 编译缓存的辅助工具

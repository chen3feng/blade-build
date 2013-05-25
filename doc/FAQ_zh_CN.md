<wiki:toc max_depth="3" />
Blade FAQ
========

运行环境
-------

### 为什么blade不能在我的平台运行？

描述：
运行blade , 报syntax error。

解决过程：

1. blade 运行需要python 2.6 以上. 请使用python -V 查看python 版本。
- 装了python 2.7还是报错，确认 ptyhon -V 看到的是新版本，必要时配置PATH环境变量或者重新登录。
- 使用env python, which python 等命令查看python命令到底用的是哪个。

### vim 编辑 BUILD 文件时没有语法高亮
 * 首先确认是否是以 install 的方式安装的
 * 然后检查 ~/.vim/syntax/blade.vim 是否存在，是否指向正确的文件
 * 然后检查 ~/.vimrc 里是否有 autocmd! BufRead,BufNewFile BUILD set filetype=blade
这条命令。
 * 如果问题还没解决，请联系我们。

### 为什么alt用不了？

描述：
alt 用不了

解决过程：

 1. 重新执行install
 - 把 ~/bin 加入到用户profile，重新登录


## 构建问题

### 为什么deps 里有写的依赖target顺序不同，编译结果不同？

描述：
//common/config/ini:ini 在某个库的deps里放置的顺序不同，放前面没有通过，放到后面通过了。

解决过程：

 * 查看编译错误输出，中间有个库su.1.0是prebuilt库。
 * //common/config/ini:ini 放在这个target 前后编译结果不一样。
 * 经查看，su.1.0 依赖//common/config/ini:ini，但是没有编译进静态库。所以
//common/config/ini:ini 放到它后面时，gcc按顺序查找能查找到symbols, 但放在
su.1.0 前就查找不到了，所以输出undefined reference.

结论：

 * 建议尽量源代码编译项目。
 * 减少prebuilt项目，prebuilt库尽量补全依赖的target。

### ccache缓存了错误信息，是不是ccache出问题了？

描述：
编译提示有错误，在源文件里修改后重新编译还是有错误，是不是ccache缓存了告警或者错误信息，没有更新出问题了 ？

解决过程：

 1. 查看ccache manual, ccache在direct mode 可能会有internal error。
 - 告知XFS同事如果再次遇到这个问题，立刻修改配置查看是否是cache自身问题。
 - 同时查看预处理cpp文件后的结果，发现头文件修改没有反映在预处理后的文件里。
 - 应该是包含路径错误，经过查找，build64_release下存在相同的头文件，而且build64_release默认是加到
-I里， 编译时默认加入 -Ibuild64_realease -I.
在build64_realease 首先查找头文件， 因此找到这个同名头文件，XFS同事放了一个文件在这个输出目录里，但是修改的却是
自己的工程文件。

结论：

 * 检查include path。

### 我只有一个没有源代码的库，如何使用
请参考[[#cc_library]]中，关于prebuilt的部分。

### prebuilt 库只有.so文件，我也只需要编译.so 库？
描述：
prebuilt 库只有.so文件，我也只需要编译.so 库

解决过程：

 1. cc_library 如果需要编译为动态库，那么只需要提供动态库。
 - cc_plugin 需要静态库。

结论：
 * 所以prebuilt库最好提供静态库和动态库。
 * 升级到最新blade。

### 手头只有无源代码的静态库，但是我们需要编译动态库
描述：
只提供了静态库，但是我们需要编译动态库 ？

解决过程：

 1. .a files are just archives of .o object files, so all you need to do is unpack the archive and repackage them as a shared object (.so)。
```bash
ar -x mylib.a
gcc -shared *.o -o mylib.so
```
 - 我们提供了脚本自动转, atoso
 - so 不能转为 .a 库。

结论：无源代码时，最好同时得到动态和静态库。

### blade支持环境变量里指定的gcc去编译项目吗？
描述：
想使用特定版本的gcc编译项目。

解决过程：

 * CC=/usr/bin/gcc CXX=/usr/bin/g++ CPP=/usr/bin/cpp LD=/usr/bin/g++ blade targets

结论：

 * 升级到最新blade且注意环境变量的配置要一致，即使用版本一致的编译器和linker。

### 我的代码已经修改了，blade编译还有问题？
描述：
在CI机器上，blade编译有error, 修复错误后从新从svn拉取，但是还是提示相同的错误。

解决过程：
 * 检查文件是否是修改后的copy.
 * 该文件由于在CI机器上是root权限，而该同事登录机器的用户名不是root, 覆盖不了原来的文件。
 * 提示错误的文件是老文件。

结论：
 * 权限切换时需要注意文件的所属者。

### 编译出来的SO库带有路径信息？
描述：
使用Blade编译出来的so库带有路径信息，使用起来麻烦，可以配置更改一下吗 ？

在一个大的项目中，不同的子项目，库完全可能重名，如果人工去协调这个问题，显然是划不来的。
因此，Blade使用库时，总是带有路径信息的，从根本上避免了这个问题。用的时候也带上路径即可。

### 为什么Blade新加的error flag 不起作用？
描述：
使用更新后的Blade编译本地项目发现error flag 没有起作用 ？

解决过程：

 1. 检查Blade是否是最新的。
 - 检查cpp程序是否把error flag 过滤了，如果不支持这个error flag, Blade 不会使用，否则编译报错。
 - 检查后发现gcc版本过低。

结论：

 * 升级gcc。

### blade -c 清除不了项目生成的文件
描述：
blade -c 清除不了项目生成的文件

解决过程：

 - 请先检查命令是否配对使用blade -prelease with blade -prelease -c , blade -pdebug with blade -pdebug -c。

结论：

 * 检查命令。

### 如何显示构建的命令行
我想看到构建过程中中执行的完整命令。
构建时加上 --verbose 参数，就能显示完整的命令行。

### 我修改了源文件，为何还是失败，报错位置也匹配不上(或者没有重新编译)?
首先 alt 到 build 目录下，看看是不是把源代码（或者头文件）放在这里了，由于 Blade 分离了源码和构建结果目录，Blade 也会到构建结果目录找源码优先，而且由于 scons 的限制，还会更优先，因此产生这样的错误，目前还没有好的解决办法。
如果是源文件误放到这里，构建时会显示 Compiling build64_release/...，根据这一点能更容易定位这个问题。

### 如何发布预编译的库?
有些机密的代码，希望以库的方式发布，但同时又依赖了非机密的库（比如common），如何发布呢？
比如这样的库：
```
cc_library(
    name = 'secrity',
    srcs = 'secrity.cpp',
    deps = [
        '//common/base/string:string',
        '//thirdparty/glog:glog',
    ]
)
```
这样发布：
修改 BUILD 文件，去掉 srcs
```
cc_library(
    name = 'secrity',
    prebuilt = True, # srcs 改为这个
    deps = [
        '//common/base/string:string',
        '//thirdparty/glog:glog',
    ]
)
```
同时对外的头文件保持不变，按照cc_library介绍中，prebuild要求的方式组织库即可。
尤其需要注意的是，deps 必须保持不变，且不要把虽然被你一来但却不属于你的项目的库作为预编译库发布出去。

### unrecognized options 是什么意思？
比如 unrecognized options {'link_all_symbols': 1}。
不同的目标有不同的选项参数，如果传了目标所不支持的参数，就会报告这个错误。可能的原因是误用了其他目标的参数，或者拼写错误，对于后一种情况，BLADE的vim语法高亮功能可以帮你更容易看到错误。

### Source file xxx.cc belongs to both xxx and yyy 是什么意思？
比如 Source file cp_test_config.cc belongs to both cc_test xcube/cp/jobcontrol:job_controller_test and cc_test xcube/cp/jobcontrol:job_context_test？

为了避免不必要的重复编译和可能的编译参数不同导致违反 C++ 的[http://en.wikipedia.org/wiki/One_Definition_Rule 一次定义规则]，通常每个源文件应该只属于一个目标，如果一个源文件被多个目标使用，应该写成单独的 cc_library，并在 deps 中依赖这个库。

### 如何开启 C++11
编辑配置文件，加入：
```
cc_config(
    cxxflags='gnu++0x'
)
```

程序故障
---------


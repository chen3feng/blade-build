# 配置

## 配置文件
Blade 只有一种配置文件格式，但是支持多重配置文件，按以下顺序依次查找和加载，后加载的配置文件里存在的配置项会覆盖前面已经加载过的配置项

* blade 安装目录下的 blade.conf，这是全局配置。
* ~/.bladerc 用户 HOME 目录下的 .bladerc 文件，这是用户级的配置。
* BLADE_ROOT 其实也是个配置文件，写在这里的是项目级配置。
* BLADE_ROOT.local 开发者自己的本地配置文件，用于临时调整参数等用途

后面描述的所有多个参数的配置的每个配置参数都有默认值，并不需要全部写出，也没有顺序要求。

配置的语法和构建规则一样，也类似函数调用，例如：
```python
global_config(
    test_timeout = 600,
)
```

### global_config
Blade全局配置

| 参数  | 类型 | 默认值 | 值域 | 说明 |
|-------|-----|-------|-----|----|
| native_builder | string | scons | ninja scons | Blade所用的后端构建系统，默认是`scons`，但是建议用`ninja` |
| duplicated_source_action |string| warning | warning error| 发现同一个源文件属于多个目标时的行为，默认为`warning`，建议设置为`error`|
| test_timeout | int | 600 | | 运行每个测试的超时时间，单位秒，超过超时值依然未结束，视为测试失败 |
| debug_info_level | string | mid |no low mid high| 生成的构建结果中调试符号的级别，支持四种级别，越高越详细，可执行文件也越大 |

[ninja](https://ninja-build.org/)是一个专注构建速度的元构建系统，经实测在构建大型项目时，
用ninja速度比scons快很多，因此后续主要基于ninja优化，并逐步淘汰对scons的支持。

### cc_config
所有c/c++目标的公共配置

| 参数  | 类型 | 默认值 | 值域 | 说明 |
|-------|-----|-------|-----|-----|
| extra_incs   | list |  [] | |额外的头文件搜索路径，比如['thirdparty']｜
| cppflags     | list |  [] | | C/C++公用编译选项 |
| cflags       | list |  [] | | C专用编译选项 |
| cxxflags     | list |  [] | | C++专用编译选项 |
| linkflags    | list |  [] | | 构建库和可执行文件以及测试时公用的链接选项，比如库搜索路径等 |
| warnings     | list | 内置 | 一般是-W开头，比如['-Wall', '-Wextra']等 | C/C++公用警告 |
| c_warnings   | list | 内置 | | 编译C代码时的专用警告 |
| cxx_warnings | list | 内置 | |编译C++代码时的专用警告 |
| optimize     | list | 内置 | | 优化专用选项，debug模式下会被忽略，比如 -O2，-omit-frame-pointer 等 |

所有选项均为可选，如果不存在，则保持先前值。发布带的blade.conf中的警告选项均经过精心挑选，建议保持。
有些编译器警告仅用于 C 或 C++，设置时注意不要放错位置。

### cc_test_config
构建和运行测试所需的配置

| 参数  | 类型 | 默认值 | 值域 | 说明 |
|-------|-----|-------|-----|-----|
| dynamic_link          |bool   | False               |True False | 测试程序是否默认动态链接，可以减少磁盘开销 |
| heap_check            |string | 空                  | [参考 gperftools 的文档](https://gperftools.github.io/gperftools/heap_checker.html) | 开启 gperftools 的 HEAPCHECK，空表示不开启 |
| gperftools_libs       |list   | ['#tcmalloc']       | | tcmclloc 库，blade deps 格式 |
| gperftools_debug_libs |list   | ['#tcmalloc_debug'] | | tcmalloc_debug 库，blade deps 格式 |
| gtest_libs            |list   | ['#gtest']          | | gtest 的库，blade deps 格式 |
| gtest_main_libs       |list   | [‘#gtest_main’]     | | gtest_main 的库路径，blade deps 格式 |

注意:

* gtest 1.6开始，去掉了 make install，但是可以绕过，参见[gtest1.6.0安装方法](http://blog.csdn.net/chengwenyao18/article/details/7181514)。
* gtest 库还依赖 pthread，因此gtest_libs需要写成 ['#gtest', '#pthread']
* 或者把源码纳入你的源码树，比如thirdparty下，就可以写成gtest_libs='//thirdparty/gtest:gtest'。

### java_config
Java构建相关的配置

| 参数  | 类型 | 默认值 | 值域 | 说明 |
|-------|-----|-------|-----|-----|
| version         | string | 空 | "6" "1.6" 等 | JDK 兼容性版本号 |
| source_version  | string | 取 version 的值 | | 提供与指定发行版的源代码版本兼容性 |
| target_version  | string | 取 version 的值 | | 生成特定 VM 版本的类文件 |
| maven           | string | 'mvn'          | | 调用 `mvn` 命令需要的路径 |
| maven_central   | string | 空             | | maven 仓库的URL
| warnings        | list   | ['-Werror', '-Xlint:all'] | | 警告设置 |
| source_encoding | string | None                      | | 设置源代码的默认编码 |
| java_home       | string | 读取 '$JAVA_HOME' 环境变量  | | 设置JAVA_HOME |

### proto_library_config
编译protobuf需要的配置

| 参数  | 类型 | 默认值 | 值域 | 说明 |
|-------|-----|-------|-----|-----|
| protoc        | string | 'protoc' |  | protoc编译器的路径 |
| protobuf_libs | list   |          |  |protobuf库的路径，Blade deps 格式 |
| protobuf_path | string |          |  | import 时的 proto 搜索路径，相对于 BLADE_ROOT |
| protobuf_include_path | string | | | 编译 pb.cc 时额外的 -I 路径 |
             
### thrift_library_config
编译thrift需要的配置

| 参数  | 类型 | 默认值 | 值域 | 说明 |
|-------|-----|-------|-----|-----|
| thrift      | string | 'thrift' | | thrift 编译器的路径 |
| thrift_libs | list   |          | | hrift库的路径，Blade deps 格式 |
| thrift_incs | list   |          | | 编译 thrift 生成的 C++ 时额外的头文件搜索路径 |
| thrift_gen_params | string | 'cpp:include_prefix,pure_enums' | | thrift 的编译参数 |

所有的 config 的列表类型的选项均支持追加模式，用法如下：

```python
cc_config(
    append = config_items(
        warnings = [...]
    )
)
```

所有这些配置项都有默认值，如果不需要覆盖就无需列入相应的参数。默认值都是假设安装到系统目录下，
如果你的项目中把这些库放进进了自己的代码中（比如我们内部），请修改相应的配置。

## 环境变量

Blade还支持以下环境变量：

* TOOLCHAIN_DIR，默认为空
* CPP，默认为cpp
* CXX，默认为g++
* CC，默认为gcc
* LD，默认为g++

TOOLCHAIN_DIR和CPP等组合起来，构成调用工具的完整路径，例如：

调用/usr/bin下的gcc（开发机上的原版gcc）
```bash
TOOLCHAIN_DIR=/usr/bin blade
```
使用clang
```bash
CPP='clang -E' CC=clang CXX=clang++ LD=clang++ blade
```

如同所有的环境变量设置规则，放在命令行前的环境变量，只对这一次调用起作用，如果要后续起作用，用 export，要持久生效，放入 ~/.profile 中。

环境变量的支持将来考虑淘汰，改为配置编译器版本的方式，因此建议仅用于临时测试不同的编译器。

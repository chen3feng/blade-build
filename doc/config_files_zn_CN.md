配置
----
Blade 支持三个配置文件，按以下顺序依次加载，后加载的配置会覆盖前面的配置

* blade 安装目录下的 blade.conf，这是全局配置。
* ~/.bladerc 用户 HOME 目录下的 .bladerc 文件，这是用户级的配置。
* BLADE_ROOT 其实也是个配置文件，写在这里的是项目级配置。
* BLADE_ROOT.local 开发者自己的本地配置文件，用于临时调整参数等用途

后面描述的所有多个参数的配置的每个配置参数都有默认值，并不需要全部写出，也没有顺序要求。

### global_config
Blade全局配置
```python
global_config(
    native_builder = 'ninja',  # 后端构建系统，目前支持scons和ninja
    duplicated_source_action = 'error',  # 发现同一个源文件属于多个目标时的行为，默认为warning
    test_timeout = 600  # 600s  # 测试超时，单位秒，超过超时值依然未结束，视为测试失败
) 
```

[ninja](https://ninja-build.org/)是一个专注构建速度的元构建系统，经实测在构建大型项目时，用ninja速度比scons快很多，因此后续主要基于ninja优化，并逐步淘汰对scons的支持。

### cc_config
所有c/c++目标的公共配置
```python
cc_config(
    extra_incs = ['thirdparty'],  # 额外的 -I，比如 thirdparty
    warnings = ['-Wall', '-Wextra'...], # C/C++公用警告
    c_warnings = ['-Wall', '-Wextra'...], # C专用警告
    cxx_warnings = ['-Wall', '-Wextra'...], # C++专用警告
    optimize = '-O2', # 优化级别
)
```
所有选项均为可选，如果不存在，则保持先前值。发布带的blade.conf中的警告选项均经过精心挑选，建议保持。

### cc_test_config
构建和运行测试所需的配置
```python
cc_test_config(
    dynamic_link=True,   # 测试程序是否默认动态链接，可以减少磁盘开销，默认为 False
    heap_check='strict', # 开启 gperftools 的 HEAPCHECK，具体取值请参考 gperftools 的文档
    gperftools_libs='//thirdparty/perftools:tcmalloc',  # tcmclloc 库，blade deps 格式
    gperftools_debug_libs='//thirdparty/perftools:tcmalloc_debug', # tcmalloc_debug 库，blade deps 格式
    gtest_libs='//thirdparty/gtest:gtest',  # gtest 的库，blade deps 格式
    gtest_main_libs='//thirdparty/gtest:gtest_main' # gtest_main 的库路径，blade deps 格式
)
```

所有的 config 的列表类型的选项均支持追加模式，用法如下：

```python
cc_config(
    append = config_items(
        warnings = [...]
    )
)
```

注意:

* gtest 1.6开始，去掉了 make install，但是可以绕过，参见[gtest1.6.0安装方法](http://blog.csdn.net/chengwenyao18/article/details/7181514)。
* gtest 库还依赖 pthread，因此gtest_libs需要写成 ['#gtest', '#pthread']
* 或者把源码纳入你的源码树，比如thirdparty下，就可以写成gtest_libs='//thirdparty/gtest:gtest'。

### proto_library_config
编译protobuf需要的配置
```python
proto_library_config(
    protoc='protoc',  # protoc编译器的路径
    protobuf_libs='//thirdparty/protobuf:protobuf', # protobuf库的路径，Blade deps 格式
    protobuf_path='thirdparty', # import 时的 proto 搜索路径，相对于 BLADE_ROOT
    protobuf_include_path = 'thirdparty',  # 编译 pb.cc 时额外的 -I 路径
)
```

### thrift_library_config
编译thrift需要的配置
```python
thrift_library_config(
    thrift='thrift',  # protoc编译器的路径
    thrift_libs='//thirdparty/thrift:thrift', # thrift库的路径，Blade deps 格式
    thrift_path='thirdparty', # thrift中include时的thrift文件的搜索路径，相对于 BLADE_ROOT
    thrift_incs = 'thirdparty',  # 编译 thrift生成的.cpp 时额外的 -I 路径
)
```

所有这些配置项都有默认值，如果不需要覆盖就无需列入相应的参数。默认值都是假设安装到系统目录下，如果你的项目中把这些库放进进了自己的代码中（比如我们内部），请修改相应的配置。

环境变量
----------

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

环境变量的支持将来考虑淘汰，改为配置编译器版本的方式，因此建议暂时不要使用。

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

你可以用 `blade dump` 命令来输出当前的配置，并根据需要修改使用：

```bash
blade dump --config --to-file my.config
```

不加 `--to-file` 选项，则输出到标准输出。

### global\_config

Blade全局配置

| 参数                       | 类型   | 默认值  | 值域               | 说明                                                                       |
|----------------------------|--------|---------|--------------------|----------------------------------------------------------------------------|
| backend\_builder           | string | ninja   | ninja              | Blade所用的后端构建系统，只支持 `ninja`                                    |
| duplicated\_source\_action | string | warning | warning, error     | 发现同一个源文件属于多个目标时的行为，默认为`warning`，建议设置为`error`   |
| test\_timeout              | int    | 600     |                    | 运行每个测试的超时时间，单位秒，超过超时值依然未结束，视为测试失败         |
| debug\_info\_level         | string | mid     | no, low, mid, high | 生成的构建结果中调试符号的级别，支持四种级别，越高越详细，可执行文件也越大 |
| build\_jobs                | int    | 0       | 0~CPU核数          | 并行构建的最大进程数量，默认会根据机器配置自动计算                         |
| test\_jobs                 | int    | 0       | 0~CPU核数/2        | 并行测试的最大进程数量，默认会根据机器配置自动计算                         |
| test\_related\_envs        | list   | []      | 字符串或正则表达式 | 是否影响增量测试的环境变量名                                               |
| run_unrepaired_tests       | bool   | False   |                    | 增量测试时，是否运行未修复的（先前已经失败且未修改的）测试                 |

Blade 一开始依赖 scons 作为后端，但是后来由于优化的需要，发现 ninja 更合适。
[ninja](https://ninja-build.org/)是一个专注构建速度的元构建系统，经实测在构建大型项目时，
用 ninja 速度比 scons 快很多，因此我们淘汰了对 scons 的支持。

### cc\_config

所有c/c++目标的公共配置

| 参数           | 类型   | 默认值   | 值域                                     | 说明                                                                |
| -------------- | ------ | -------- | ------                                   | ------------------------                                            |
| extra\_incs    | list   | []       |                                          | 额外的头文件搜索路径，比如['thirdparty']                            |
| cppflags       | list   | []       |                                          | C/C++公用编译选项                                                   |
| cflags         | list   | []       |                                          | C专用编译选项                                                       |
| cxxflags       | list   | []       |                                          | C++专用编译选项                                                     |
| linkflags      | list   | []       |                                          | 构建库和可执行文件以及测试时公用的链接选项，比如库搜索路径等        |
| warnings       | list   | 内置     | 一般是-W开头，比如['-Wall', '-Wextra']等 | C/C++公用警告                                                       |
| c\_warnings    | list   | 内置     |                                          | 编译C代码时的专用警告                                               |
| cxx\_warnings  | list   | 内置     |                                          | 编译C++代码时的专用警告                                             |
| optimize       | list   | 内置     |                                          | 优化专用选项，debug模式下会被忽略，比如 -O2，-omit-frame-pointer 等 |
| hdr\_dep\_missing\_severity | string | warning | info, warning, error         | 对头文件所属的库的依赖的缺失的严重性                                |

所有选项均为可选，如果不存在，则保持先前值。发布带的blade.conf中的警告选项均经过精心挑选，建议保持。
有些编译器警告仅用于 C 或 C++，设置时注意不要放错位置。单独分出 optimize 选项是因为这些选项在 debug 模式下需要被忽略。

### cc_library_config

C/C++ 库的配置

| 参数                       | 类型   | 默认值    | 值域                        | 说明                                                                       |
|----------------------------|--------|-----------|-----------------------------|----------------------------------------------------------------------------|
| prebuilt_libpath_pattern   | string |lib${bits} |                             | 预构建的库所在的子目录名的模式                                             |
| hdr_dep_missing_severity   | string | warning   | debug, info, warning, error | 当检查到包含了头文件却缺少了对其所属库的依赖时，报错的严重性               |

Blade 支持生成多个目标平台的目标，比如在 x64 环境下，支持通过命令行参数的 -m 参数编译 32 位和 64 位 目标。
因此 prebuilt_libpath_pattern 是一个模式，其中包含可替换的变量：

- ${bit} 目标执行位数，比如 32，64。
- ${arch} CPU 架构名，比如 i386, x86_64 等。

这样就可以在不同的子目录中同时存放多个目标平台的库文件而不冲突。本属性也可以为空，表示没有子目录（库文件就放在当前 BUILD 文件所在的目录）。
如果只构建一个平台的目标，可以只有一个目录甚至根本不用子目录。

### cc\_test\_config

构建和运行测试所需的配置

| 参数                     | 类型     | 默认值                | 值域                                                                                | 说明                                         |
| ------------------------ | -------- | --------------------- | ------                                                                              | -------------------------------------------- |
| dynamic\_link            | bool     | False                 |                                                                                     | 测试程序是否默认动态链接，可以减少磁盘开销   |
| heap\_check              | string   | 空                    | [参考 gperftools 的文档](https://gperftools.github.io/gperftools/heap_checker.html) | 开启 gperftools 的 HEAPCHECK，空表示不开启   |
| gperftools\_libs         | list     | ['#tcmalloc']         |                                                                                     | tcmclloc 库，blade deps 格式                 |
| gperftools\_debug\_`libs | list     | ['#tcmalloc\_debug']  |                                                                                     | tcmalloc\_debug 库，blade deps 格式          |
| gtest\_libs              | list     | ['#gtest']            |                                                                                     | gtest 的库，blade deps 格式                  |
| gtest\_main\_libs        | list     | [‘#gtest\_main’]      |                                                                                     | gtest\_main 的库路径，blade deps 格式        |

注意:

* gtest 1.6开始，去掉了 make install，但是可以绕过，参见[gtest1.6.0安装方法](http://blog.csdn.net/chengwenyao18/article/details/7181514)。
* gtest 库还依赖 pthread，因此gtest\_libs需要写成 ['#gtest', '#pthread']
* 或者把源码纳入你的源码树，比如thirdparty下，就可以写成gtest\_libs='//thirdparty/gtest:gtest'。

### java\_config

Java构建相关的配置

| 参数                              | 类型   | 默认值                      | 值域         | 说明                                 |
|--------------------------------   |--------|-----------------------------|--------------|--------------------------------------|
| version                           | string | 空                          | "6" "1.6" 等 | JDK 兼容性版本号                     |
| source\_version                   | string | 取 version 的值             |              | 提供与指定发行版的源代码版本兼容性   |
| target\_version                   | string | 取 version 的值             |              | 生成特定 VM 版本的类文件             |
| maven                             | string | 'mvn'                       |              | 调用 `mvn` 命令需要的路径            |
| maven\_central                    | string | 空                          |              | maven 仓库的URL                      |
| maven\_snapshot\_update\_policy   | string | daily                       |              | maven 仓库的 SNAPSHOT 版本的更新策略 |
| maven\_snapshot\_update\_interval | int    | 空                          |              | maven 仓库的 SNAPSHOT 版本的更新间隔 |
| warnings                          | list   | ['-Werror', '-Xlint:all']   |              | 警告设置                             |
| source\_encoding                  | string | None                        |              | 设置源代码的默认编码                 |
| java\_home                        | string | 读取 '$JAVA\_HOME' 环境变量  |              | 设置JAVA_HOME                        |

关于 Maven：

* maven\_snapshot\_updata\_policy 允许的值："always", "daily"(默认), "interval",  "never"
* maven\_snapshot\_update\_interval 的单位为分钟。语义遵守[Maven文档](https://maven.apache.org/ref/3.6.3/maven-settings/settings.html)

### proto\_library\_config

编译protobuf需要的配置

| 参数                    | 类型   | 默认值   | 值域 | 说明                                           |
|-------                  |-----   |-------   |----- |-----                                           |
| protoc                  | string | 'protoc' |      | protoc编译器的路径                             |
| protobuf\_libs          | list   |          |      | protobuf库的路径，Blade deps 格式              |
| protobuf\_path          | string |          |      | import 时的 proto 搜索路径，相对于 BLADE\_ROOT |
| protobuf\_include\_path | string |          |      | 编译 pb.cc 时额外的 -I 路径                    |

### thrift\_library\_config

编译thrift需要的配置

| 参数                | 类型   | 默认值                            | 值域 | 说明                                          |
|-------------------  |--------|---------------------------------  |------|-----------------------------------------------|
| thrift              | string | 'thrift'                          |      | thrift 编译器的路径                           |
| thrift\_libs        | list   |                                   |      | hrift库的路径，Blade deps 格式                |
| thrift\_incs        | list   |                                   |      | 编译 thrift 生成的 C++ 时额外的头文件搜索路径 |
| thrift\_gen\_params | string | 'cpp:include\_prefix,pure\_enums' |      | thrift 的编译参数                             |

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

* TOOLCHAIN\_DIR，默认为空
* CPP，默认为cpp
* CXX，默认为g++
* CC，默认为gcc
* LD，默认为g++

TOOLCHAIN\_DIR和CPP等组合起来，构成调用工具的完整路径，例如：

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

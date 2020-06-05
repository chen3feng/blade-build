# Configuration

## configuration file

Blade supports three configuration files, which are loaded in the following order. The loaded configuration will overwrite the previous configuration.

* blade.conf in the blade installation directory, this is the global configuration.
* ~/.bladerc The .bladerc file in the user's HOME directory, which is a user-level configuration.
* BLADE_ROOT is actually a configuration file, written here is a project-level configuration.
* BLADE_ROOT.local developer's own local configuration file for temporary adjustment of parameters, etc.

Each configuration parameter of the configuration of all the multiple parameters described later has a default value, and does not need to be completely written or ordered.

You can run `blade dump` command to dump current configuration, and modify it as your need:

```bash
blade dump --config --to-file my.config
```

Without the `--to-file` option, the result will be dumped to stdout.

### global_config

Blade global configuration

```python
global_config(
    backend_builder = 'ninja', # backend build system, only supports ninja now.
    duplicated_source_action = 'error', # When the same source file is found to belong to multiple targets, the default is warning
    test_timeout = 600 # 600s # test timeout, in seconds, the timeout value is still not over, it is considered a test failure
)
```

| parameter                  | type   | default | values             | description                                                                                |
|----------------------------|--------|---------|--------------------|----------------------------------------------------------------------------                |
| backend\_builder           | string | ninja   | ninja              | Backend build system, only `ninja` currently                                               |
| duplicated\_source\_action | string | warning | warning, error     | The action when the same source file is found to belong to multiple targets                |
| test\_timeout              | int    | 600     |                    | in seconds, tests which can't finish in this seconds will be reported as fail              |
| debug\_info\_level         | string | mid     | no, low, mid, high | Debug information level, the higher may be helpful for debugging, but cost more disk space |
| build\_jobs                | int    | 0       | 0~#CPU cores       | The number of concurrent build jobs, 0 means decided by blade itself                       |
| test\_jobs                 | int    | 0       | 0~#CPU cores/2     | The number of concurrent build jobs, 0 means decided by blade itself                       |

[ninja](https://ninja-build.org/) is a meta-construction system that focuses on building speeds.
We used to use scons as the backend, but ninja is much faster, so the we only use ninja as backend, and the support for scons is removed.

### cc_config

Common configuration of all c/c++ targets

| parameter      | type   | default  | values                                   | description              |
| -------------- | ------ | -------- | ------                                   | ------------------------ |
| extra\_incs    | list   | []       |                                          | header file search paths |
| cppflags       | list   | []       |                                          | C/C++ common options     |
| cflags         | list   | []       |                                          | C only options           |
| cxxflags       | list   | []       |                                          | C++ only options         |
| linkflags      | list   | []       |                                          | Link options             |
| warnings       | list   | 内置     | -Wxxx such as ['-Wall', '-Wextra']       | C/C++ common warnings    |
| c\_warnings    | list   | 内置     |                                          | C only warnings          |
| cxx\_warnings  | list   | 内置     |                                          | C++ only warnings        |
| optimize       | list   | 内置     |                                          | optimize options         |

All options are optional and if they do not exist, the previous value is maintained. The warning options in the release of blade.conf are carefully selected and recommended to be maintained.
The optimize flags is separate from other compile flags because it is ignored in debug mode.

Example:

```python
cc_config(
    extra_incs = ['thirdparty'], # extra -I, like thirdparty
    warnings = ['-Wall', '-Wextra'...], # C/C++ Public Warning
    c_warnings = ['-Wall', '-Wextra'...], # C special warning
    cxx_warnings = ['-Wall', '-Wextra'...], # C++ Dedicated warning
    optimize = ['-O2'], # optimization level
)
```

All options are optional and if they do not exist, the previous value is maintained. The warning options in the release of blade.conf are carefully selected and recommended to be maintained.

### cc_test_config

The configuration required to build and run the test

```python
cc_test_config(
    dynamic_link=True, # Test program default dynamic link, can reduce disk overhead, the default is False
    heap_check='strict', # Open HEAPCHECK of gperftools. For details, please refer to the documentation of gperftools.
    gperftools_libs='//thirdparty/perftools:tcmalloc', # tcmclloc library, blade deps format
    gperftools_debug_libs='//thirdparty/perftools:tcmalloc_debug', # tcmalloc_debug library, blade deps format
    gtest_libs='//thirdparty/gtest:gtest', #gtest library, blade deps format
    gtest_main_libs='//thirdparty/gtest:gtest_main' # gtest_main library path, blade deps format
)
```

note:

* gtest 1.6 starts, remove install install, but can be bypassed, see [gtest1.6.0 installation method](http://blog.csdn.net/chengwenyao18/article/details/7181514).
* The gtest library also relies on pthreads, so gtest_libs needs to be written as ['#gtest', '#pthread']
* Or include the source code in your source tree, such as thirdparty, you can write gtest_libs='//thirdparty/gtest:gtest'.

### java_config

Java related configurations

| param                          | type   | default                   | value          | description                                             |
|--------------------------------|--------|---------------------------|----------------|---------------------------------------------------------|
| version                        | string | empty                     | "6" "1.6", ... | Provide compatibility with specified release            |
| source_version                 | string | take `version`            |                | Provide source compatibility with specified release     |
| target_version                 | string | take `version`            |                | Generate class files for specific VM version            |
| maven                          | string | 'mvn'                     |                | The command to run `mvn`                                |
| maven_central                  | string |                           |                | Maven repository URL                                    |
| maven_snapshot_update_policy   | string | daily                     |                | Update policy of snapshot version in maven repository   |
| maven_snapshot_update_interval | int    | empty                     |                | Update interval of snapshot version in maven repository |
| warnings                       | list   | ['-Werror', '-Xlint:all'] |                | Warning flags                                           |
| source_encoding                | string | None                      |                | Specify character encoding used by source files         |
| java_home                      | string | Take from '$JAVA_HOME'    |                | Set JAVA_HOME                                           |

About maven:

* maven_snapshot_updata_policy values: "always", "daily"(default), "interval",  "never"
* maven_snapshot_update_interval is in minutes。See [Maven Documents](https://maven.apache.org/ref/3.6.3/maven-settings/settings.html) for details.

### proto_library_config

Compile the configuration required by protobuf

```python
proto_library_config(
    protoc='protoc', #protoc compiler path
    protobuf_libs='//thirdparty/protobuf:protobuf', #protobuf library path, Blade deps format
    protobuf_path='thirdparty', # import proto search path, relative to BLADE_ROOT
    protobuf_include_path = 'thirdparty', # extra -I path when compiling pb.cc
)
```

### thrift_library_config

Compile the configuration required by thrift

```python
thrift_library_config(
    thrift='thrift', #protoc compiler path
    thrift_libs='//thirdparty/thrift:thrift', #thrift library path, Blade deps format
    thrift_path='thirdparty', # thrift include the search path for the thrift file, as opposed to BLADE_ROOT
    thrift_incs = 'thirdparty', # compile thrift generated .cpp extra -I path
)
```

All config's list type options support append mode, as follows:

```python
cc_config(
    append = config_items(
        Warnings = [...]
    )
)
```

All of these configuration items have default values, and you don't need to include the appropriate parameters if you don't need to override them.
The default config values of libraries are assumed to be installed in the system directory.
If you put these libraries into your own code in your project (such as our internals), please modify the corresponding configuration.

### cc_library_config

C/C++ library configuration

| parameter                  | type   | default   | values             | description                                                                |
|----------------------------|--------|-----------|--------------------|----------------------------------------------------------------------------|
| prebuilt_libpath_pattern   | string |lib${bits} |                    | The pattern of prebuilt library subdirectory                               |

Blade suppor built target for different platforms, such as, under the x64 linux, you can build 32/64 bit targets with the -m option.
So, prebuilt_libpath_pattern is really a pattern, allow some variables which can be substituted:

- ${bit}  Target bits, such as 32，64。
- ${arch} Target CPU architecture name, such as i386, x86_64 等。

In this way, library files of multiple target platforms can be stored in different subdirectories
without conflict. This attribute can also be empty string, which means no subdirectory.
If you only concern to one target platform, it is sure OK to have only one directory or have no directory at all.

## Environment Variable

Blade also supports the following environment variables:

* TOOLCHAIN_DIR, default is empty
* CPP, default is cpp
* CXX, defaults to g++
* CC, the default is gcc
* LD, default is g++

TOOLCHAIN_DIR and CPP are combined to form the full path of the calling tool, for example:

Call gcc under /usr/bin (original gcc on development machine)

```bash
TOOLCHAIN_DIR=/usr/bin blade
```

Using clang

```bash
CPP='clang -E' CC=clang CXX=clang++ LD=clang++ blade
```

As with all environment variable setting rules, the environment variables placed before the command line only work for this call. If you want to follow up, use export, and make it last forever, put it in ~/.profile.

Support for environment variables will be removed in the future, instead of configuring the compiler version, so it is recommended to only use it to test different compilers temporarily.

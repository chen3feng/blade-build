# Configuration

## configuration file
Blade supports three configuration files, which are loaded in the following order. The loaded configuration will overwrite the previous configuration.

* blade.conf in the blade installation directory, this is the global configuration.
* ~/.bladerc The .bladerc file in the user's HOME directory, which is a user-level configuration.
* BLADE_ROOT is actually a configuration file, written here is a project-level configuration.
* BLADE_ROOT.local developer's own local configuration file for temporary adjustment of parameters, etc.

Each configuration parameter of the configuration of all the multiple parameters described later has a default value, and does not need to be completely written or ordered.

### global_config
Blade global configuration
```python
global_config(
    native_builder = 'ninja', # backend build system, currently supports scons and ninja
    duplicated_source_action = 'error', # When the same source file is found to belong to multiple targets, the default is warning
    test_timeout = 600 # 600s # test timeout, in seconds, the timeout value is still not over, it is considered a test failure
)
```

[ninja](https://ninja-build.org/) is a meta-construction system that focuses on building speeds.
The speed of using ninja is much faster than scons, so the follow-up is mainly based on ninja optimization, and the support for scons is gradually eliminated.

### cc_config
Common configuration of all c/c++ targets
```python
cc_config(
    extra_incs = ['thirdparty'], # extra -I, like thirdparty
    warnings = ['-Wall', '-Wextra'...], # C/C++ Public Warning
    c_warnings = ['-Wall', '-Wextra'...], # C special warning
    cxx_warnings = ['-Wall', '-Wextra'...], # C++ Dedicated warning
    optimize = '-O2', # optimization level
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

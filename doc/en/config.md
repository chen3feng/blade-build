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

``

| parameter                  | type   | default | values             | description                                                                                |
|----------------------------|--------|---------|--------------------|----------------------------------------------------------------------------                |
| backend\_builder           | string | ninja   | ninja              | Backend build system, only `ninja` currently                                               |
| duplicated\_source\_action | string | warning | warning, error     | The action when the same source file is found to belong to multiple targets                |
| test\_timeout              | int    | 600     |                    | in seconds, tests which can't finish in this seconds will be reported as fail              |
| debug\_info\_level         | string | mid     | no, low, mid, high | Debug information level, the higher may be helpful for debugging, but cost more disk space |
| build\_jobs                | int    | 0       | 0~#CPU cores       | The number of concurrent build jobs, 0 means decided by blade itself                       |
| test\_jobs                 | int    | 0       | 0~#CPU cores/2     | The number of concurrent test jobs, 0 means decided by blade itself                        |
| test\_related\_envs        | list   | []      | string or regex    | Environment variables which will affect tests during incremental test                      |
| run_unrepaired_tests       | bool   | False   |                    | Whether run unrepaired(no changw after previous failure) tests during incremental test     |

[ninja](https://ninja-build.org/) is a meta-construction system that focuses on building speeds.
We used to use scons as the backend, but ninja is much faster, so the we only use ninja as backend, and the support for scons is removed.

Example:

```python
global_config(
    backend_builder = 'ninja', # backend build system, only supports ninja now.
    duplicated_source_action = 'error', # When the same source file is found to belong to multiple targets, the default is warning
    test_timeout = 600 # 600s # test timeout, in seconds, the timeout value is still not over, it is considered a test failure
)
```

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
| hdr\_dep\_missing\_severity | string | warning | info, warning, error         | The severity of the missing dependency on the library to which the header file belongs |
| hdr_dep_missing_ignore     | dict   | {}        | see below                   | The ignored list when verify missing dependency for a included header file              |

All options are optional and if they do not exist, the previous value is maintained. The warning options in the release of blade.conf are carefully selected and recommended to be maintained.
The optimize flags is separate from other compile flags because it is ignored in debug mode.

The `hdr_dep_missing_severity` and `hdr_dep_missing_ignore` control the header file dependency missing verification behavior.
See [`cc_library.hdrs`](build_rules/cc.md#cc_library) for details.

The format of `hdr_dep_missing_ignore` is a dict like `{ target_label : {src : [headers] }`, for example:

```python
{
    'common:rpc' : {'rpc_server.cc':['common/base64.h', 'common/list.h']},
}
```

Which means, for `common:rpc`, in `rpc_server.cc`, if the libraries which declared `common/base64.h`
and `common/list.h` are not declared in the `deps`, this error will be ignored.

For the generated header files, the path can have no build_dir prefix, and it is best not to have it, so that it can be used for different build types.

This feature is to help upgrade old projects that do not properly declare and comply with header file dependencies.

To make the upgrade process easier, for all header missing errors, we write them into `blade-bin/blade_hdr_verify.details` file, with this format.

So you can copy it to somewhere and load it in you `BLADE_ROOT`:

```python
cc_config(
    hdr_dep_missing_ignore = eval(open('blade_hdr_verify.details').read()),
)
```

In this way, existing header file dependency missing errors will be suppressed, but new ones will be reported normally.

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
| maven_jar_allowed_dirs         | list   | empty                     |                | Directories and subdirectors which `maven_jar` is allowed |
| maven_jar_allowed_dirs_exempts | list   | empty                     |                | Targets which are exempted from the `maven_jar_allowed_dirs` check |
| maven_snapshot_update_policy   | string | daily                     |                | Update policy of snapshot version in maven repository   |
| maven_snapshot_update_interval | int    | empty                     |                | Update interval of snapshot version in maven repository |
| maven_download_concurrency     | int    | 0                         |                | Number of processes when download maven artifacts       |
| warnings                       | list   | ['-Werror', '-Xlint:all'] |                | Warning flags                                           |
| source_encoding                | string | None                      |                | Specify character encoding used by source files         |
| java_home                      | string | Take from '$JAVA_HOME'    |                | Set JAVA_HOME                                           |

About maven:

* Valid values of `maven_snapshot_updata_policy` are: "always", "daily"(default), "interval",  "never"
* The unit of `maven_snapshot_update_interval` is minutes。See [Maven Documents](https://maven.apache.org/ref/3.6.3/maven-settings/settings.html) for details.
* Setting `maven_download_concurrency` to above `1` can speedup maven artifacts downloading, but [maven local repository is not concurrent-safe defaultly](https://issues.apache.org/jira/browse/MNG-2802),
  you can try to install [takari](http://takari.io/book/30-team-maven.html#concurrent-safe-local-repository) to make it safe.
  NOTE there are multiple available versions, the version in the example code of the document is not the latest one.
* In order to avoid duplication of descriptions of maven artificts with the same id in the code base, and version redundancy and conflicts,
  it is recommended to set `maven_jar_allowed_dirs` to prohibit calling `maven_jar` outside these directories and their subdirectories.
  Existing `maven_jar` targets that have escaped outside the desired directories can be exempted by the `maven_jar_allowed_dirs_exempts` configuration item.
  We also provide an auxiliary tool [`collect-disallowed-maven-jars.py`](../../tool) to easily generate this list.
  If there are too many entries, it is recommended to load them from a separate file:

  ```python
  java_config(
      maven_jar_allowed_dirs_exempts = eval(open('exempted_maven_jars.conf').read()),
  )
  ```

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

| parameter                  | type   | default   | values                      | description                                              |
|----------------------------|--------|-----------|-----------------------------|----------------------------------------------------------|
| prebuilt_libpath_pattern   | string |lib${bits} |                             | The pattern of prebuilt library subdirectory             |
| hdrs_missing_severity      | string | error     | debug, info, warning, error | The severity of missing `cc_library.hdrs`                |
| hdrs_missing_suppress      | list   | []        | list of targets             | List of target labels to be suppressed for above problem |

Blade suppor built target for different platforms, such as, under the x64 linux, you can build 32/64 bit targets with the -m option.
So, prebuilt_libpath_pattern is really a pattern, allow some variables which can be substituted:

* ${bit}  Target bits, such as 32，64。
* ${arch} Target CPU architecture name, such as i386, x86_64 等。

In this way, library files of multiple target platforms can be stored in different subdirectories
without conflict. This attribute can also be empty string, which means no subdirectory.
If you only concern to one target platform, it is sure OK to have only one directory or have no directory at all.

The format of `hdrs_missing_suppress` is a list of build targets (do not have a'//' at the beginning).
We also provide an auxiliary tool [`collect-hdrs-missing.py`](../../tool) to easily generate this list.
If there are too many entries, it is recommended to load them from a separated file:

```python
cc_library_config(
    hdrs_missing_suppress = eval(open('blade_hdr_missing_spppress').read()),
)
```

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

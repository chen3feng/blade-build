# Upgrade to V2

## Features

There are many improvement in V2, include performance，new features, code refactoring. You can get such benefits from V2:

- Full functional java and scala building
- Header files are included in dependency mangement.
- Support describe libraries which built by other build systems such as Autotool and CMake by using the new `foegign_cc_library` rule
- Support custom extensions. you can write you own extension and using `include` function to load it
- Many performance optimizations
- Better diagnostic message include BUILD file path and line number, you can jump into BUILD files in editors now.
- Support self profile and diagnostic
- Support show slow build targets and tests
- Support quiet mode (by the `--quite` option), just show progress bar when nothing is wrong.
- Better `clean` sub command
- Complete English documents.

## Possible Problems

### Python Version

V2 only support python 2.7 and 3.x, no longer support old versions. And for python 3.x, only 3.6 and 3.9 were tests.

### Ninja

Blade is a "meta" build system, it must depends on a backend build system.
The initial version use `Scons` as its backend. But after years, we found that `ninja` is much faster than Scons.
So in V2, we only support ninja as our backend build system.

To upgrade to V2, you muse install [ninja](https://ninja-build.org/), by either package manager or downloaded binary.

### Header Files Dependency Check

Header file are included in dependency management in V2 defaultly.
If you use V2 to build old projects which were built by V1.x, many diagnostic errors will occur.
You can fix or suppress these legancy errors. or turn off this check totally (strongly discouraged!).
See [config](config.md) and [cc rules](build_rules/cc.md) for details.

### Target Visibility Control

[Visibility](build_file.md) of the target is private by default. Targets is only visible to other
ones in same `BUILD` file defaultly. This feature can be disabled [globally](config.md#global_config),
or only check new added build targets by exempting the existing ones.

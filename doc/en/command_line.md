# Command line reference

## Basic Command Line Syntax

```bash
Blade <subcommand> [options]... [targets]...
```

## subcommand

Subcommand is a subcommand that currently has:

* build means build project
* test means build and run unit test
* clean indicates the result of the cleanup target
* query query target dependencies and dependencies
* run build and run a single target

## Target syntax

Targets is a separate list of spaces, supported formats:

* path:name represents a target in the path
* path indicates all targets in the path
* path/... represents all targets in the path, and recursively includes all subdirectories
* :name indicates a target in the current directory

If no target is specified, it defaults to all targets in the current directory (excluding subdirectories). If there is no BUILD file in the current directory, it will fail.
When you specify ... as the end target, if its path exists, it will not fail even if the expansion is empty.

## Subcommand options

The options supported by different subcommands are different. Please run blade \<subcommand\> --help to view

Here are some common command line options

* -m32,-m64 specifies the number of build target digits, the default is automatic detection
* -p PROFILE specifies debug/release, default release
* -k, --keep-going encountered an error during the build process to continue execution (if it is a fatal error can not continue)
* -j N, --jobs=N N way parallel build (Blade defaults to parallel build, calculate the appropriate value by yourself)
* -t N, --test-jobs=N N-way parallel test, applicable on multi-CPU machines
* --verbose complete command output for each command line
* –h, --help show help
* --color=yes/no/auto Whether to turn on color
* --generate-dynamic Forces the generation of dynamic libraries
* --generate-java generates java files for proto_library and swig_library
* --generate-php generates php files for proto_library and swig_library
* --gprof supports GNU gprof
* --coverage supports generation of coverage and currently supports GNU gcov and Java jacoco

## example

```bash
# Build all targets in the current directory, not including subdirectories
blade build

# Build all the targets in the current directory and subdirectories
blade build ...

# Build a target named `urllib` in the current directory
blade build :urllib

# Build and test all targets from the WORKPACE root, common and all its subdirectories

blade test //common/...
blade test base/...

# Build and test the target named `string_test` in the base subdirectory
blade test base:string_test
```

Blade will search `BUILD` files recursively for the `...` target pattern, if some dirs should be
excluded from searching, you can put an empty `.bladeskip` under it.

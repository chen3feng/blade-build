# Write a BUILD file

The Blade passes a series of files named "BUILD" (all uppercase), which need to be written by the developer. Each BUILD file describes the source file of a target, other targets it depends on, and other properties through a set of object description functions.

## Example of a BUILD file

Building a script is simple:

Example: common/base/string/BUILD
```python
cc_library(
    name = 'string',
    srcs = [
        'algorithm.cpp',
        'string_number.cpp',
        'string_piece.cpp',
        'format.cpp',
        'concat.cpp'
    ],
    deps = ['//common/base:int']
)
```
It is also an explanation, just need to list the target name, source file name and dependency name (may not be).

## Style suggestion
* Four spaces are indented, do not use tab characters
* Always use single quotes
* Target name is lowercase
* The file names in src are in alphabetical order
* Deps writes the dependencies (:target) in this directory first, and then writes (//dir:name) in other directories, in alphabetical order.
* A line between different targets, can be annotated before
* An empty # after the comment #, such as # This is a comment

## Common Attributes
Blade uses a set of target functions to define targets. The common properties of these targets are:

 * name: string, together with the path to become the unique identifier of the target, also determines the output name of the build
 * srcs: list or string, the source file needed to build the object, usually in the current directory, or in a subdirectory relative to the current directory
 * deps: list or string, other targets on which the object depends

The allowed format of deps:

 * "//path/to/dir/:name" target in other directories, path is the path from BLADE_ROOT, and name is the target name to be relied upon. When you see it, you know where it is.
 * ":name" The target, path in the current BUILD file can be omitted.
 * "#name" system library. Write # with the name directly, such as #pthread, #z respectively equivalent to link -lpthread and -lz on the command line, but will be passed to other targets that depend on this library.

## Building rules (IN CHINESE, TO BE TRANSLATED)

### [Building C/C++ Goals](build_rules/cc.md)
### [Building protobuf and thrift](build_rules/idl.md)
### [Building Java](build_rules/java.md)
### [Building Scala](build_rules/scala.md)
### [Building Python](build_rules/python.md)
### [Building Lex and Yacc](build_rules/lexyacc.md)
### [Build SWIG](build_rules/swig.md)
### [Bash test](build_rules/shell.md)
### [Custom Build Rules](build_rules/gen_rule.md)
### [File Packaging](build_rules/package.md)

## Other features

### [Custom Build Rules](include.md)

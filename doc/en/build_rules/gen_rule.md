# Custom Build Rules

## gen\_rule

Used to customize your own construction rules, parameters:
-outs: list, output file list
-cmd: str, the called command line, may contain the following variables, which will be replaced with actual values before running:
    - $SRCS, space-separated list of source file names, relative to WORKSPACE
    - $OUTS, space-separated list of output files, relative to WORKSPACE
    - $SRC\_DIR, the directory where the input file is located
    - $OUT\_DIR, the directory where the output file is located
    - $FIRST\_SRC, first input file path
    - $FIRST\_OUT, the path of the first output file
    - BUILD\_DIR, The root output directory, such as build[64,32]\_[release, debug]

- cmd\_name: str, the name of the command, used to display in simplified mode, the default is `COMMAND`
- generate\_hdrs: bool, indicates whether this target will generate C/C++ header files other than the file names already listed in `outs`.
  If a C/C ++ target depends on the gen\_rule target that generates header files, then these header files need to be generated before compilation can begin.
  gen\_rule will automatically analyze whether there are header files in `outs`, so there is no need to set it if all of the headers are listed in `outs`.
  This option will reduce the parallelism of compilation, because if a target can be divided into mutiple stages, such as:
    - generating source code (including header files)
    - compiling
    - generating library
  When the header file list is given accurately, after the first stage is generated, other targets can be built without waiting the whole target is built.
- heavy: bool, indicates this a "heavy" target, that is, it will consume a lot of CPU or memory, making it impossible to parallel with other tasks or too much.
  Turning on this option will reduce build performance, but will help reduce build failures caused by insufficient resources.

Example:
```python
gen_rule(
    name='test_gen_target',
    cmd='echo what_a_nice_day;touch test2.c',
    deps=[':test_gen'],
    outs=['test2.c']
)
````

NOTE: `gen_rule` only writes `outs` files in the subdir of BUILD_DIR, but when you use `gen_rule`
to generate source code and want to reference the generated source code in other targets, just
consider them as if they are generated in the source tree, without the BUILD_DIR prefix.

Multiple similar gen\_rule can be considered to be defined as an extension maintained in a separate
`bld` file, and through [include] (../include.md)Functions are introduced to reduce code redundancy
and better maintenance.

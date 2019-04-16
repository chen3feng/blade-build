Blade FAQ
========

# Running environment

## Why can't blade run on my platform?

description:
Run blade and report syntax error.

Solution process:

1. The blade needs to run python 2.7 or higher. Please use python -V to view the python version.
- Installed python 2.7 or reported an error, confirm that ptyhon -V sees the new version, configure the PATH environment variable if necessary or log in again.
- Use env python, which python and other commands to see which python command is used.

## vim No syntax highlighting when editing BUILD files
 * First confirm whether it is installed by install
 * Then check if ~/.vim/syntax/blade.vim exists and points to the correct file
 * Then check if there is autocmd in the ~/.vimrc! BufRead, BufNewFile BUILD set filetype=blade
This order.
 * If the problem has not been resolved, please contact us.

## Why can't alt be used?

description:
Alt can't use

Solution process:

 1. Re-execute the install
 - Add ~/bin to the user profile and log in again


# Building problem

## Why do the dependencies in the deps have different target sequences, and the compilation results are different?

description:
//common/config/ini:ini The order of placement in a library's deps is different. It is not passed before, and passed to the back.

Solution process:

 * View compilation error output, there is a library in the middle su.1.0 is a prebuilt library.
 * //common/config/ini:ini The compilation result is different before and after this target.
 * After viewing, su.1.0 relies on //common/config/ini:ini, but it is not compiled into a static library. and so
//common/config/ini:ini When it is placed behind it, gcc looks up in order to find symbols, but puts
It can't be found before su.1.0, so the output is undefined reference.

in conclusion:

 * It is recommended to compile the project as much as possible.
 * Reduce the prebuilt project, the prebuilt library tries to complete the dependent target.

## ccache cached the error message, is there a problem with ccache?

description:
There is an error in the compile prompt. After re-compiling in the source file, there is still an error. Is ccache buffering the alarm or error message, and there is no update?

Solution process:

 1. Check ccache manual, ccache may have an internal error in direct mode.
 - If you encounter this problem again, immediately modify the configuration to see if it is a cache itself.
 - At the same time, the results of pre-processing the cpp file are checked, and it is found that the header file modification is not reflected in the pre-processed file.
 - It should contain the path error. After searching, the same header file exists under build64_release, and build64_release is added by default.
-I, compile time by default -Ibuild64_realease -I.
In the build64_realease first find the header file, so find the header file of the same name, XFS colleagues put a file in this output directory, but the modification is
Your own project file.

in conclusion:

 * Check include path.

## I only have one library without source code, how to use it
Please refer to [[#cc_library]] for the prebuilt part.

## prebuilt library only .so files, I only need to compile the .so library?
description:
The prebuilt library has only .so files, and I only need to compile the .so library.

Solution process:

 1. cc_library If you need to compile to a dynamic library, you only need to provide a dynamic library.
 - cc_plugin requires a static library.

in conclusion:
 * So the prebuilt library is best to provide static and dynamic libraries.
 * Upgrade to the latest blade.

## There is only a static library of passive code, but we need to compile the dynamic library.
description:
Only static libraries are provided, but do we need to compile dynamic libraries?

Solution process:

 1. .a files are just archives of .o object files, so all you need to do is unpack the archive and repackage them as a shared object (.so).
```bash
ar -x mylib.a
gcc -shared *.o -o mylib.so
```
 - We provide script auto-transfer, atoso
 - so can't be converted to .a library.

Conclusion: When it comes to passive code, it's best to get both dynamic and static libraries.

## bladeSupport the gcc specified in the environment variable to compile the project?
description:
I want to compile a project with a specific version of gcc.

Solution process:

 * CC=/usr/bin/gcc CXX=/usr/bin/g++ CPP=/usr/bin/cpp LD=/usr/bin/g++ blade targets

in conclusion:

 * Upgrade to the latest blade and note that the configuration of the environment variables is the same, that is, use the same version of the compiler and linker.

## My code has been modified, there is still a problem with blade compilation?
description:
On the CI machine, the blade compiles with an error. After fixing the error, it is pulled from the svn, but it still prompts the same error.

Solution process:
 * Check if the file is a modified copy.
 * The file is rooted on the CI machine, and the user name of the colleague logging in to the machine is not root and cannot overwrite the original file.
 * The file that indicated the error is an old file.

in conclusion:
 * Pay attention to the owner of the file when switching permissions.

## Compiled SO library with path information?
description:
The so library compiled with Blade has path information, which is troublesome to use. Can you configure changes?

In a large project, different sub-projects, the library may be completely re-named, if the problem is manually coordinated, it is obviously not worth mentioning.
Therefore, when Blade uses the library, it always has path information, which fundamentally avoids this problem. You can also take the path when you use it.

## Why does the new error flag of Blade not work?
description:
Compiling the local project with the updated Blade found that the error flag didn't work?

Solution process:

 1. Check if the Blade is up to date.
 - Check if the cpp program filters the error flag. If the error flag is not supported, Blade will not use it, otherwise the compiler will report an error.
 - Check that the gcc version is too low.

in conclusion:

 * Upgrade gcc.

## blade -c Can't clear files generated by the project
description:
Blade -c can't clear the files generated by the project

Solution process:

 - Please check if the command is paired with blade -prelease with blade -prelease -c , blade -pdebug with blade -pdebug -c.

in conclusion:

 * Check the command.

## How to display the command line of the build
I want to see the complete command executed during the build process.
The complete command line can be displayed by adding the --verbose parameter to the build.

## I modified the source file, why is it still failing, and the error location is not matched (or not recompiled)?
First alt to the build directory to see if the source code (or header file) is placed here, because the Blade separates the source code and builds the results directory.
Blade will also go to the build results directory to find the source code first, and because of the limitations of scons, it will be given priority, so there is no good solution.
If the source file is misplaced here, the build will show Compiling build64_release/..., which makes it easier to locate the problem.

## How do I publish a precompiled library?
Some confidential code, I hope to release it as a library, but at the same time rely on non-confidential libraries (such as common), how to publish it?
Such a library:
```python
cc_library(
    name = 'secrity',
    srcs = 'secrity.cpp',
    deps = [
        '//common/base/string:string',
        '//thirdparty/glog:glog',
    ]
)
```
So released:
Modify the BUILD file and remove the srcs
```python
cc_library(
    name = 'secrity',
    prebuilt = True, # srcs changed to this
    deps = [
        '//common/base/string:string',
        '//thirdparty/glog:glog',
    ]
)
```
At the same time, the external header file remains unchanged. According to the cc_library introduction, the prebuild requires the organization of the library.
It's important to note that deps must remain the same, and don't publish libraries that are owned by you but not yours as pre-compiled libraries.

## unrecognized options What does this mean?
For example unrecognized options {'link_all_symbols': 1}.
Different targets have different option parameters, and this error is reported if a parameter that is not supported by the target is passed. Possible cause is misuse of other targets
The parameters, or spelling errors, for the latter case, BLADE's vim syntax highlighting feature can help you see the error more easily.

## Source file xxx.cc belongs to both xxx and yyy What does this mean?
For example, Source file cp_test_config.cc belongs to both cc_test xcube/cp/jobcontrol:job_controller_test and cc_test xcube/cp/jobcontrol:job_context_test?

In order to avoid unnecessary repetitive compilation and possible different compilation parameters, it violates C++'s [one-time definition rule](http://en.wikipedia.org/wiki/One_Definition_Rule).
Usually each source file should belong to only one target. If a source file is used by multiple targets, it should be written as a separate cc_library and depend on this library in deps.

## How to open C++11
Edit the configuration file and add:
```
cc_config(
    cxxflags='gnu++0x'
)
```

## Compiled results take up too much disk space
Projects built with Blades are often relatively large-scale projects, so the results after construction often take up more space. If you have problems in this area, you can try to optimize them in the following way.
```python
# Reduce the overhead of debugging symbols
global_config(
    debug_info_level = 'no'
)
Description:
No: no debugging symbols, the program can not debug gdb
Low: low debug symbol, you can see the function name and global variables
Mid: medium, more local variables than low, function parameters
High: highest, contains debugging information such as macros

# Test program uses dynamic links
```python
cc_test_config(
    dynamic_link = True
)
The test program is not used for publishing. Dynamic linking can reduce a lot of disk overhead. If a specific test dynamic link fails, you can specify dynamic_link = False for it separately.
```

### Generate "thin" static library
Gnu ar supports the generation of static libraries of type 'thin', which is different from regular static libraries. The thin static library only records the path of the .o file, which can reduce the space occupation to a large extent.
However, this kind of library can't be used for publishing. Fortunately, in the scenario of using blade, static libraries are generally used only inside the build system.

The practice is to modify the cc_library_config.arflags parameter, plus the `T` option:
```python
cc_library_config(
    arflags = 'rcsT'
)
```

## cannot find -lstdc++
Maybe you need to install a static version of libstdc++
```
yum install libstdc++-static
```

# C/C++ Rules

cc_`*` targets
The common CC attributes are：

| Attribute | Description | Example | Comments |
|------|-----|-----|------|
| warning | whether suppress all warnings  | warning='no' | the default values is 'yes', so can be omitted |
| defs | user define macros | defs=['_MT'] | Can also has value, eg. 'A=1' |
| incs | header search paths | incs=['poppy/myinc'] | Usually used for thirdparty library, use full include path in our code is more recommended |
| optimize | optimize flags | optimize=['O3'] | ignored in the debug mode |
| extra_cppflags | extra C/C++ compile flags | extra_cppflags=['-Wno-format-literal'] | many useful flags, such as `-g`，`-fPIC` are builtin |
| extra_linkflags | extra link flags | extra_linkflags=['-fopenmp'] | many useful flags such `-g` are already built in |

* There is a separated `optimize` attribute from the `extra_cppflags`, because it should be ignored
  in the debug mode, otherwise it will hinder debugging. but for some kind of libraries, which are
  mature enough and performance related, we rarely debug trace into them, such as hash, compress,
  crypto, you can specify `always_optimize = True`.

* There are 3 phrases in the C/C++ building: preprocessing, compiling, linking. with different flags.

## cc_library

Build a C/C++ library

`cc_library` can be used to build static and dynamic library. But only the static library will built default, unless it is depended by a dynamic_linked cc_binary, or run blade build with `--generate-dynamic`.

Example:
```python
cc_library(
    name='lowercase',
    srcs=['./src/lower/plowercase.cpp'],
    deps=['#pthread'],
    link_all_symbols=False
)
```

Attributes:

* link_all_symbols=True
  If you depends on the global initialization to register something, but didn't access these
  global object. it works for code in `srcs` of executable. but if it is in a library, it will be
  discarded at the link time because linker find it is unsed.

  This attribute tells the linker don't discard any unused symbols in this library even if it seems
  to be unused.
  
  You'd better put these self-registering code into a separated small library. otherwise, the whole
  library will be linked into the executable unconditionally, increase the size of the executable.

  Youi also need to know, the `link_all_symbols` is the attribute of the library, not the user of it.
  Click [here](https://stackoverflow.com/questions/805555/ld-linker-question-the-whole-archive-option) to learn more details if you have interesting.

* always_optimize
True: Always optimize.
False: Don't optimize in debug mode。
The default value is False。It only apply to cc_library.

* prebuilt=True
For libraries without source code, library should be put under the lib{32,64} sub dir accordingly.

* export_incs
Similar to `incs`, but it is transitive for all targets depends on it, even if indirect depends on it.

NOTE:

There is no dependency code in the generated cc_library, both static and dynamic. But for the
dynamic library, it contains the paths of dependencies.

These libraries can just be used locally (such as run tests)，not fit for the production environment.
If you want to build a shared library can be use in the environment, you should use `cc_plugin`,
which will include the code from it dependencies.

## cc_binary
Build executable from source.
Example:
```python
cc_binary(
    name='prstr',
    srcs=['./src/mystr_main/mystring.cpp'],
    deps=['#pthread',':lowercase',':uppercase','#dl'],
)
```

* dynamic_link=False
  cc_binary is static linked defaultly for easy deploying, include libstdc++.
  For some [technology limitation](https://stackoverflow.com/questions/8140439/why-would-it-be-impossible-to-fully-statically-link-an-application)，
  glibc is not static linked. we can link it statically, but there are still some problems.

  If you want to generate a dynamic linked executable, you can set it to True，all dependency
  libraries will be linked statically, except prebuilt libraries if they has no dynamic version.
  This may reduce disk usage, but program will startup slower. Usually it can be use for local
  testing, but it didn't fit for deploy.

* export_dynamic=True
  Usually, dynamic library will only access symbols from its dependencies. but for some special
  case, shared library need to access symbols defined in the host executable, so come the attribute.

  This attribute tells linker to put all symbols into its dynamic symbol table. make them visible
   for loaded shared libraries. for more details, see `--export-dynamic` in man ld(1).

## cc_test
cc_binary, with gtest gtest_main be linked automatically,

Test will be ran in a test sandbox, it can't access source code directly.
If you want to pass some data files into it, you must need `testdata` attribute.

* testdata=[]
Copy test data files into the test sandbox, make them visible to the test code.
This attribute supports the following forms:
 * 'file'
Use the original filename in test code.
 * '//your_proj/path/file'
Use "your_proj/path/file" form to access in test code.
 * ('//your_proj/path/file', "new_name")
Use the "new_name" in test code.

Example:
```python
cc_test(
    name = 'textfile_test',
    srcs = 'textfile_test.cpp',
    deps = ':io',
    testdata = [
        'test_dos.txt',
        '//your_proj/path/file',
        ('//your_proj/path/file', 'new_name')
    ]
)
```

## cc_plugin

Link all denendencies into the generated `so` file, make it can be easily loaded in other languages.
```python
cc_plugin(
    name='mystring',
    srcs=['./src/mystr/mystring.cpp'],
    deps=['#pthread',':lowercase',':uppercase','#dl'],
    warning='no',
    defs=['_MT'],
    optimize=['O3']
)
```

cc_plugin is designed for create extension, such as JNI and python extension.

## resource_library
Compile static data file to be resource, which can be accessed in the program directly.

When we deploy a program, it often requires many other files to be deployed together. it's often boring.
Blade support `resource_library`, make it quite easy to put resource files into the executable easily.
For example, put there static pages into a library：
```python
resource_library(
    name = 'static_resource',
    srcs = [
        'static/favicon.ico',
        'static/forms.html',
        'static/forms.js',
        'static/jquery-1.4.2.min.js',
        'static/jquery.json-2.2.min.js',
        'static/methods.html',
        'static/poppy.html'
    ]
)
```
It will generate a library `libstatic_resource.a`，and a header file `static_resource.h`(with full include path)。

When you need tp use it, you need to include `static_resource.h`(with full path from workspace root)
and also "common/base/static_resource.h"，

Use STATIC_RESOURCE macro to simplify access to the data (defined in "common/base/static_resource.h"):
```c
StringPiece data = STATIC_RESOURCE(poppy_static_favicon_ico);
```
The argument of STATIC_RESOURCE is the full path of the data file, and replace all of the
non-alphanum and hyphen character to unserscore(`_`):

The data is readonly static storage. can be accessed in any time.

NOTE:
There is a little drawback for static resource, it can;t be updated at the runtime, so consider it before using.

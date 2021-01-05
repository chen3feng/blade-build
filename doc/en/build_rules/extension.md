# Extension

Although `gen_rule` has allowed us to customize some build rules, it will be more concise
and convenient to define extensions for scenarios that need to be reused.

## Define Extension

Suppose we want to support an awesome file type, first compile it into a C file, and then compile
it into `cc_library`, we can define the build rule in a `awesome_build_rules.bld` file:

```python
def awesome_library(name, srcs=[], deps=[]):
     cc_srcs = [src + '.c' for src in srcs]
     gen_rule(name=name+'_cc', srcs=srcs, outs=cc_srcs, cmd=<...>)
     cc_library(name=name, srcs=cc_srcs, deps=deps)
```

Remember the `gen_rule` is a useful native rule when you create your own rules.

You can also define constants：

```python
GTEST_LIBS = ["//thirdparty/gtest:gtest"]
```

### Suggested Style

- Using the `.bld` extension name
- Using the `_` prefix for private symbols

## Use Extension

We support 2 ways to load extensions into `BUILD` file, `load` and `incluce`.
In both ways, The loaded symbols are only **visible to current `BUILD` file**.

These function supports the path of the subdirectory relative to the current directory and
the path of the relative workspace starting with `//`.

### the `load` function

Load extension and import symbols into current `BUILD` file.

Prototype：

```python
def load(extension_label, *symbols, **aliases):
```

`symbols` are the symbol names to be imported.
`aliases` are the symbol names to be imported as aliases.

Use:

```python
include('//common/awesome_build_rules.bld')

awesome_library(  # Use imported rule
     name='awesome_lib',
     srcs=['my.awesome', 'your.awesome'],
)
```

Globals symbols such as functions and constants can be imported.

Alias mechanism can be used to resolve name conflicts:

```python
load('//common/awesome_build_rules1.bld', my_awesome_library='awesome_library')
load('//common/awesome_build_rules2.bld', your_awesome_library='awesome_library')
```

The symbols in BUILD file is inaccessible in the extension file.

## The `include` function

The `include` function is like the `#include` directive in C language, it include the file content into current `BUILD` file.

Use:

```python
include('//common/awesome_build_rules.bld')
...
```

You should use `load` rather than `include` in most case.

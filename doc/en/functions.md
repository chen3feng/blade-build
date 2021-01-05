# Build Functions #

Some Functions can be called in BUILD files.

## include ##

Include custom constants and functions

You can use the `include` function to include custom constants and functions

definition:

Suppose we want to support an awesome file type, first compile it into a c file, and then compile it into cc_library, then define the build rule file awesome_build_rules.bld

```python
def awesome_library(name, srcs=[], deps=[]):
     cc_srcs = [src + '.c' for src in srcs]
     gen_rule(name=name+'_cc', srcs=srcs, outs=cc_srcs, cmd=<...>)
     cc_library(name=name, srcs=cc_srcs, deps=deps)
```

use:

In some BUILD file:

```python
include('//common/awesome_build_rules.bld')

awesome_library(
     name='awesome_lib',
     srcs=['my.awesome', 'your.awesome'],
)
```

After including, the definitions in the included file will be visiable in the current `BUILD` file. The `include` function supports the path of the subdirectory relative to the current directory and the path of the relative workspace starting with `//`. The included definitions only **apply to the current `BUILD` file**.

## glob ##

```python
glob(include, exclude=[], allow_empty=False)
```

Glob is a helper function that finds all files that match certain path patterns in the source dir, and returns a list of their paths.
Patterns may contain shell-like wildcards, such as * , ? , or [charset]. Additionally, the path element '**' matches any subpath.
You can use `exclude` to exclude some files.

Example:

```python
...
    srcs = glob(['*.java', 'src/main/java/**/*.java'], exclude=['*Test.java'])
...
```

Usually, it is an error for glob to return an empty result, but you can specify `allow_empty=True` to eliminate this error if it is surely you expected.

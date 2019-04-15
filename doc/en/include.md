# Import custom constants and functions

You can use the `include` function to import custom constants and functions

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
Include('//common/awesome_build_rules.bld')

awesome_library(
     name='awesome_lib',
     srcs=['my.awesome', 'your.awesome'],
)
```
After the include, the definition of the imported file will be imported into the current BUILD file. The include supports the path of the subdirectory relative to the current directory and the path of the relative workspace starting with //, and is only valid for the current file BUILD.

Importing custom constants and functions is a more advanced feature, so use it with caution.

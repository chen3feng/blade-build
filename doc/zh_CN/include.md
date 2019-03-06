导入自定义常量和函数

include函数用于导入自定义常量和函数

定义：

假设我们要支持一种awesome文件类型，先编译成c文件，再编译成cc_library，那么定义构建规则文件awesome_build_rules.bld
```python
def awesome_library(name, srcs=[], deps=[]):
    cc_srcs = [src + '.c' for src in srcs]
    gen_rule(name=name+'_cc', srcs=srcs, outs=cc_srcs, cmd=<...>)
    cc_library(name=name, srcs=cc_srcs, deps=deps)
```

使用：

In some BUILD file:
```python
include('//common/awesome_build_rules.bld')

awesome_library(
    name='awesome_lib',
    srcs=['my.awesome', 'your.awesome'],
)
```
include后，被导入的文件的定义均会被导入到当前BUILD文件中，include支持相对当前目录的子目录路径和//开头的相对workspace的路径，并仅对当前文件BUILD有效。

导入自定义常量和函数属于比较高级的功能，请谨慎使用。

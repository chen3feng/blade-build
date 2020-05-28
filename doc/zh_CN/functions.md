# 构建函数

一些 BUILD 文件中可以调用的函数

# include

include 函数用于导入自定义常量和函数

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

# glob

```python
glob(include, exclude=[], allow_empty=False)
```
Glob 是一个返回在源代码目录中匹配某些模式的文件的辅助函数。模式可以包含一些 shell 样式的通配符，比如`*`、`?` 和 `[字符集]`、，另外，`**` 匹配任意级别的子目录。
你可以用 `exclude` 来排除一些文件。include 和 exclude 都支持 list。

示例：
```python
...
    srcs = glob(['*.java', 'src/main/java/**/*.java'], exclude=['*Test.java'])
...
```

通常 glob 函数返回空结果视为错误，但是如果确实是符合你的预期，可以通过指定 `allow=True` 来消除。

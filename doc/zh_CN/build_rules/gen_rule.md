# 自定义规则构建

## gen\_rule

用于定制自己的构建规则，参数：
- outs list，输出的文件列表
- cmd str，被调用的命令行，可含有如下变量，运行前会被替换为实际的值：
    - $SRCS 空格分开的源文件名列表，相对 WORKSPACE
    - $OUTS 空格分开的输出文件列表，相对 WORKSPACE
    - $SRC\_DIR 输入文件所在的目录
    - $OUT\_DIR 输出文件所在的目录
    - $FIRST\_SRC 第一个输入文件的路径
    - $FIRST\_OUT 第一个输出文件的路径
    - $BUILD\_DIR 输出的根目录，比如 build[64,32]\_[release,debug]

- cmd\_name，命令的名字，用于简略模式下显示，默认为`COMMAND`
- generate\_hdrs bool，指示这个目标是否会生成 outs 里列出的文件名之外的 C/C++ 头文件。
  如果一个 C/C++ 目标依赖会生成头文件的 gen\_rule 目标，那么需要这些头文件生成后才能开始编译。
  gen\_rule 会自动分析 outs 里是否有头文件，就不需要设置。
  此选项会降低编译的并行度，因为如果一个目标如果可以分为生成源代码（其中包含头文件）和编译以及生成库
  三个阶段，那么精确给出头文件列表时，在第一阶段的头文件生成后，其他的目标就可以开始构建了，而不用等待
  该目标全部构建完成。
- heavy: bool 这是不是一个‘重’目标，也就是会消耗大量的 CPU 或内存，使得不能和其他任务并行或者并行太多。
  开启本选项会降低构建性能，但是有助于减少资源不足导致的构建失败。

```python
gen_rule(
    name='test_gen_target',
    cmd='echo what_a_nice_day;touch test2.c',
    deps=[':test_gen'],                         # 可以有deps , 也可以被别的target依赖
    outs=['test2.c']
)
````

注意：
`gen_rule` 只会把输出文件生成在相应的结果输出目录下，不会污染源代码树。但是如果你在其他目标中引用
`gen_rule` 生成的源文件时，只需要假设这些文件是生成在源代码目录下，不需要考虑结果目录前缀。

多个相似的 gen\_rule 可以考虑定义为扩展在单独的`bld`文件中维护，并通过 [include](../include.md)
函数来来引入，以减少代码冗余并更好维护。

# 自定义规则构建

## gen_rule

用于定制自己的目标
outs = []，表示输出的文件列表，需要填写这个域gen_rule才会被执行
cmd, 字符串，表示被调用的命令行
cmd中可含有如下变量，运行时会被替换成srcs和outs中的对应值
$SRCS
$OUTS
$FIRST_SRC
$FIRST_OUT
$BUILD_DIR -- 可被替换为 build[64,32]_[release,debug] 输出目录

```python
gen_rule(
    name='test_gen_target',
    cmd='echo what_a_nice_day;touch test2.c',
    deps=[':test_gen'],                         # 可以有deps , 也可以被别的target依赖
    outs=['test2.c']
)
````

很多用户使用gen_rule动态生成代码文件然后和某个cc_library或者cc_binary一起编译，
需要注意应该尽量在输出目录生成代码文件,如build64_debug下，并且文件的路径名要写对，
如 outs = ['websearch2/project_example/module_1/file_2.cc'], 这样使用
gen_rule生成的文件和库一起编译时就不会发生找不到动态生成的代码文件问题了。

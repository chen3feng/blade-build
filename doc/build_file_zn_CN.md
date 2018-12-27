# 编写BUILD文件
--------

Blade 通过一系列的名字为 "BUILD" 的文件（文件名全大写），这些文件需要开发者去编写。每个 BUILD文件通过一组目标描述函数描述了一个目标的源文件，所依赖的其他目标，以及其他一些属性。

## BUILD文件的示例

构建脚本很简单：

范例：common/base/string/BUILD
```python
cc_library(
    name = 'string',
    srcs = [
        'algorithm.cpp',
        'string_number.cpp',
        'string_piece.cpp',
        'format.cpp',
        'concat.cpp'
    ],
    deps = ['//common/base:int']
)
```
也是说明式的，只需要列出目标名，源文件名和依赖名（可以没有）即可。

## 风格建议
---------
* 四空格缩进，不要用tab字符
* 总是用单引号
* 目标名用小写
* src 里的文件名按字母顺序排列
* deps 里先写本目录内的依赖（:target），后写其他目录内的（//dir:name），分别按字母顺序排列。
* 不同目标之间空一行，前面可以加注释
* 注释的 # 后面空一格，比如 # This is a comment

## 通用属性
Blade用一组target函数来定义目标，这些target的通用属性有：

 * name: 字符串，和路径一起成为target的唯一标识，也决定了构建的输出命名
 * srcs: 列表或字符串，构建该对象需要的源文件，一般在当前目录，或相对于当前目录的子目录中
 * deps: 列表或字符串，该对象所依赖的其它targets

deps的允许的格式：

 * "//path/to/dir/:name" 其他目录下的target，path为从BLADE_ROOT出发的路径，name为被依赖的目标名。看见就知道在哪里。
 * ":name" 当前BUILD文件内的target， path可以省略。
 * "#pthread" 系统库。直接写#跟名字即可。

## 构建规则

### [构建C/C++目标](build_rules/cc.md)
### [构建protobuf和thrift](build_rules/idl.md)
### [构建Java](build_rules/java.md)
### [构建Scala](build_rules/scala.md)
### [构建Python](build_rules/python.md)
### [构建SWIG](build_rules/swig.md)
### [Bash测试](build_rules/shell.md)
### [自定义规则构建](build_rules/gen_rule.md)
### [文件打包](build_rules/package.md)

## 其他特性

### [自定义构建规则](include.md)

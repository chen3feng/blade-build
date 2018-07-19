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

cc_`*` 目标
包括 cc_test, cc_binary, cc_library，CC 目标均支持的参数为：

 * srcs 源文件列表
 * deps 依赖列表
 * incs 头文件路径列表
 * defs 宏定义列表
 * warning 警告设置
 * optimize 优化设置

* 注：thirdparty是我们代码库里的一个特殊目录，里面的代码都是一些第三方库，按照台风系统的代码规范，只允许对这里的代码用incs, defs和warnings，自己开发的代码要按照规范组织。Blade会对这个目录之外的代码使用这些参数发出警告。

|| *字段* || *解释* || *举例* || *备注* ||
|| warning || 是否屏蔽warning  || warning='no' || 默认不屏蔽 warning='yes' , 默认不用写，已开启 ||
|| defs || 用户定义的宏加入编译中 || defs=['_MT'] || 如果用户定义C++关键字，报warning ||
|| incs || 用户定义的include || incs=['poppy/myinc'] || 用户通常不要使用 ||
|| optimize || 用户定义的optimize flags || optimize=['O3'] || 适用于 cc_library cc_binary cc_test proto_library swig_library  cc_plugin resource_library ||

## 构建规则

### [构建C/C++目标](build_rules/cc.md)
### [构建protobuf和thrift](build_rules/idl.md)
### [构建Java](build_rules/java.md)
### [构建Scala](build_rules/scala.md)
### [构建SWIG](build_rules/swig.md)
### [自定义规则构建](build_rules/gen_rule.md)

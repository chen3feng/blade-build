# C/C++规则

cc_`*` 目标
CC 目标均支持的属性为：

| 属性 | 解释 | 举例 | 备注 |
|------|-----|-----|------|
| warning | 是否屏蔽warning  | warning='no' | 默认不屏蔽 warning='yes' , 默认不用写，已开启 |
| defs | 用户定义的宏加入编译中 | defs=['_MT'] | A=1 |
| incs | 增加编译源文件时的头文件查找路径 | incs=['poppy/myinc'] | 一般用于第三方库，用户代码建议使用全路径include，不要使用该属性 |
| optimize | 用户定义的optimize flags | optimize=['O3'] | 适用于 cc_library cc_binary cc_test proto_library swig_library  cc_plugin resource_library |

## cc_library

用于描述C++库目标。
cc_library同时用于构建静态和动态库，默认只构建静态库，只有被dynamic_link=1的cc_binary依赖时或者命令行指定
--generate-dynamic 才生成动态链接库。

举例：
```python
cc_library(
    name='lowercase',
    srcs=['./src/lower/plowercase.cpp'],
    deps=['#pthread'],
    link_all_symbols=False
)
```

属性：

* link_all_symbols=True
库在被静态链接时，确保库里所有的符号都被链接，以保证依赖全局对象构造函数，比如自动注册器的代码能够正常工作。
需要全部链接的部分最好单独拆分出来做成全部链接的库，而不是整个库全都全部链接，否则会无端增大可执行文件的大小。 需要注意的是，link_all_symbols是库自身的属性，不是使用库时的属性。Blade是为大型项目设计的，基于以下因素，我们提倡任何模块都应该有自己的 cc_library，用户程序都应该在deps里写全直接依赖，不提倡创建像boost那样的全头文件的库。
 * 编译速度
 * 将来未知的改变，比如某库一开始只需要头文件就能使用，不依赖标准库之外的任何库，但是后来依赖了MD5，所有使用这个库的代码都要加上新产生的依赖，这与我们设计Blade的初衷是违背的。

要强制用户这样使用，可以在编写代码时，总是编写 .h 对应的 .cpp 文件，并把一部分必然要用到的符号（函数，静态变量）的实现写在里面，即使对于模板库，可以引入一个非模板的基类，或者把非模板部分的实现放到 .cpp 里。

* always_optimize
True: 不论debug版本还是release版本总是被优化。
False: debug版本不作优化。
默认为False。目前只对cc_library有效。

* prebuilt=True
主要应用在thirdparty中从rpm包解来的库，使用这个参数表示不从源码构建。对应的二进制文件必须存在 lib{32,64}_{release,debug} 这样的子目录中。不区分debug/release时可以只有两个实际的目录。

* export_incs
类似incs，但是不仅作用于本目标，还会传递给依赖这个库的目标 | incs=['poppy/myinc'] |，和incs一样，用户代码不建议使用

##### cc_binary
定义C++可执行文件目标
```python
cc_binary(
    name='prstr',
    srcs=['./src/mystr_main/mystring.cpp'],
    deps=['#pthread',':lowercase',':uppercase','#dl'],
)
```

* dynamic_link=True
目前我们的binary默认为全静态编译以适应云计算平台使用。
如果有应用需要动态编译方式，可以使用此参数指定，此时被此target依赖的所有库都会自动生成对应的动态库供链接。
需要注意的是，dynamic_link只适用于可执行文件，不适用于库。

* export_dynamic=True
常规情况下，so中只引用所依赖的so中的符号，但是对于应用特殊的场合，需要在so中引用宿主可执行文件中的符号，就需要这个选项。
这个选项告诉连接器在可执行文件的动态符号表中加入所有的符号，而不只是用到的其他动态库中的符号。这样就使得在dlopen方式加载的so中可以调用可执行文件中的这些符号。
详情请参考 man ld(1) 中查找 --export-dynamic 的说明。

## cc_test
相当于cc_binary，再加上自动链接gtest和gtest_main
还支持testdata参数， 列表或字符串，文件会被链接到输出所在目录name.runfiles子目录下，比如：testdata/a.txt =>name.runfiles/testdata/a.txt
用blade test子命令，会在成功构建后到name.runfiles目录下自动运行，并输出总结信息。

* testdata=[]
在name.runfiles里建立symbolic link指向工程目录的文件，目前支持
以下几种形式

 * 'file'
在测试程序中使用这个名字本身的形式来访问
 * '//your_proj/path/file'
在测试程序中用"your_proj/path/file"来访问。
 * ('//your_proj/path/file', "new_name")
在测试程序中用"new_name"来访问

可以根据需要自行选择，这些路径都也可以是目录。
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

## lex_yacc_library

srcs 必须为二元列表，后缀分别为ll和yy
构建时自动调用flex和bison, 并且编译成对应的cc_library

```python
lex_yacc_library(
     name = 'parser',
     srcs = [
         'line_parser.ll',
         'line_parser.yy'
     ],
     deps = [
         ":xcubetools",
     ],
     recursive = True
)
```

* recursive=True
生成可重入的C scanner.

## cc_plugin

把所有依赖的库都静态链接到成的so文件，供其他语言环境动态加载。
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

cc_plugin 是为 JNI，python 扩展等需要动态库的场合设计的，不应该用于其他目的。

## resource_library
把数据文件编译成静态资源，可以在程序中中读取。

大家都遇到过部署一个可执行程序，还要附带一堆辅助文件才能运行起来的情况吧？
blade通过resource_library，支持把程序运行所需要的数据文件也打包到可执行文件里，
比如poppy下的BUILD文件里用的静态资源：
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
生成  和 libstatic_resource.a 或者 libstatic_resource.so。
就像一样protobuf那样，编译后后生成一个库libstatic_resource.a，和一个相应的头文件static_resource.h，带路径包含进来即可使用。

在程序中需要包含static_resource.h（带上相对于BLADE_ROOT的路径）和"common/base/static_resource.hpp"，
用 STATIC_RESOURCE 宏来引用数据：
```c
StringPiece data = STATIC_RESOURCE(poppy_static_favicon_ico);
```
STATIC_RESOURCE 的参数是从BLADE_ROOT目录开始的数据文件的文件名，把所有非字母数字和下划线的字符都替换为_。

得到的 data 在程序运行期间一直存在，只可读取，不可写入。

用 static resource 在某些情况下也有一点不方便：就是不能在运行期间更新，因此是否使用，需要根据具体场景自己权衡。



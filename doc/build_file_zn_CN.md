编写BUILD文件
--------

Blade 通过一系列的名字为 "BUILD" 的文件（文件名全大写），这些文件需要开发者去编写。每个 BUILD文件通过一组目标描述函数描述了一个目标的源文件，所依赖的其他目标，以及其他一些属性。

### BUILD文件的示例

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

风格建议
---------
* 四空格缩进，不要用tab字符
* 总是用单引号
* 目标名用小写
* src 里的文件名按字母顺序排列
* deps 里先写本目录内的依赖（:target），后写其他目录内的（//dir:name），分别按字母顺序排列。
* 不同目标之间空一行，前面可以加注释
* 注释的 # 后面空一格，比如 # This is a comment

### 描述目标

#### 通用规则
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


#### C/C++规则
##### cc_library

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

参数：

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

##### cc_test
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

##### lex_yacc_library

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

##### cc_plugin

支持生成target所依赖的库都是静态库.a的so库，即plugin。
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

##### resource_library
编译静态资源。

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


#### 构建protobuf和thrift
##### proto_library
用于定义protobuf目标
deps 为import所涉及的其他proto_library
自动依赖protobuf，使用者不需要再显式指定。
构建时自动调用protoc生成cc和h，并且编译成对应的cc_library
```python
proto_library(
    name = 'rpc_meta_info_proto',
    srcs = 'rpc_meta_info.proto',
    deps = ':rpc_option_proto',
)
```
Blade支持proto_library，使得在项目中使用protobuf十分方便。

要引用某 proto 文件生成的头文件，需要从 BLADE_ROOT 的目录开始，只是把 proto 扩展名改为 pb.h 扩展名。
比如 //common/base/string_test.proto 生成的头文件，路径为 "common/base/string_test.pb.h"。

##### thrift_library
用于定义thrift库目标
deps 为import所涉及的其他thrift_library
自动依赖thrift，使用者不需要再显式指定。
构建时自动调用thrift命令生成cpp和h，并且编译成对应的cc_library

```python
thrift_library(
    name = 'shared_thrift',
    srcs = 'shared.thrift',
)
thrift_library(
    name = 'tutorial_thrift',
    srcs = 'tutorial.thrift',
    deps = ':shared_thrift'
)
```

C++中使用生成的头文件时，规则类似proto，需要带上相对BLADE_ROOT的目录前缀。
 * thrift 0.9版（之前版本未测）有个[https://issues.apache.org/jira/browse/THRIFT-1859 bug]，需要修正才能使用，此bug已经在开发版本中[https://builds.apache.org/job/Thrift/633/changes#detail13 修正]

####swig_library

根据.i文件生成相应的python, java 和php cxx模块代码，并且生成对应语言的代码。

```python
swig_library(
    name = 'poppy_client',
    srcs = [
        'poppy_client.i'
    ],
    deps = [
        ':poppy_swig_wrap'
    ],
    warning='yes',
    java_package='com.soso.poppy.swig',   # 生成的java文件的所在package名称
    java_lib_packed=1, # 表示把生成的libpoppy_client_java.so打包到依赖者的jar包里，如java_jar依赖这个swig_library
    optimize=['O3']    # 编译优化选项
)
```

* warning
这里的warning仅仅指swig编译参数cpperraswarn是否被指定了，swig_library默认使用非标准编译告警级别（没有那么严格）。

#### Java构建
##### java_library

把java源代码编译为库。
```python
java_library(
    name = 'poppy_java_client',
    srcs = [
        glob('src/com/soso/poppy/*/*.Java)'
    ],
    deps = [
        '//poppy:rpc_meta_info_proto',       # 可以依赖proto_library生成的java文件一起编译打包
        '//poppy:rpc_option_proto',
        '//poppy:rpc_message_proto',
        '//poppy:poppy_client',              # 可以依赖swig_library生成的java文件一起编译打包
        './lib:protobuf-java',               # 可以依赖别的jar包
    ]
)
```

java_library还支持
* prebuilt=True
主要应用在已经编译打包好的java jar 包。
```python
java_library(                                                                                        
    name = 'parquet-column-gdt',                                                                     
    prebuilt = True,                                                                                 
    binary_jar = 'parquet-column-1.9.1-SNAPSHOT.jar',                                                
) 
```

Blade还支持使用来自maven的库
##### maven_jar
maven_jar (
  name = 'hadoop-common-2.7.2-tdw',
  id = 'org.apache.hadoop:hadoop-common:2.7.2-tdw-1.0.1',  # 完整的maven artifact id
  transitive = False,  # 是否自动透传其依赖
)

##### java_binary
把java源代码编译为可执行文件。
```python
java_binary(
    name = 'poppy_java_example',
    srcs = [
        glob('src/com/soso/poppy/*/*.Java)'
    ],
    deps = [
        '//poppy:poppy_java_client',
        '//poppy:rpc_example_proto',
    ]
)
```

##### java_test
编译和运行java测试代码。
```python
java_test(
    name = 'poppy_java_test',
    srcs = [
        glob('test/com/soso/poppy/*/×Test.Java)'
    ],
    deps = [
        '//poppy:poppy_java_client',
        './lib:junit',
    ]
)
```

#### 自定义规则
##### gen_rule

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

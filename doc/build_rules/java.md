# 构建Java目标

blade 早期的开发主要是针对 C/C++/Protobuf 相关的后台服务项目，作为通用的构建系统，也逐步扩展了支持 Java/Python 等的规则。第一版 Java 规则的实现（java_jar_target.py）比较简单，后由于项目需要，参考 Maven/Buck/Bazel 的实现和 Java 语言项目构建习惯和运行场景，重写了新的 Java 构建规则（java_targets.py）

## java_library

把java源代码编译为库（jar 包）。
```python
java_library(
    name = 'rpc',
    srcs = glob([
        'src/main/java/**/*.java',
    ], excludes = [
        '*Test.java'
    ]),
    resources = [
        'src/main/resources/log4j.properties',
        'resources/rpc.conf',
        'resources/services.xml'
    ],
    deps = [
        '//common/rpc:rpc_error_code_proto'         # 可以依赖proto_library生成的java文件一起编译打包
        '//common/rpc:rpc_options_proto',
        '//poppy:poppy_client',                     # 可以依赖swig_library生成的java文件一起编译打包
        '//common/net/http/java:http_utilities',    # 可以依赖别的 java_library 目标
        '//thirdparty/java/deps:slf4j',             # 依赖第三方包
        '//thirdparty/java/deps:guava',
        '//thirdparty/java/deps:netty-4.0.36.final',
    ]
)
```

- srcs 属性与 glob 函数

srcs 属性和普通规则的 srcs 属性相同，可以指明源文件的路径，遵照 java 开发习惯，比如在 Maven 中无需指定源文件列表，所有源文件按照标准目录布局组织放于 src/main/java 目录下，因此在 blade 中提供了 glob 函数用于自动获取文件列表并支持文件排除：

```python
glob([
    '*.java',                           # * 表示匹配当前目录下的 java 文件
    'src/main/java/**/*.java',          # ** 表示递归目录，规则与 python3 中的 pathlib 相同
], excludes=['*Test.java'])             # excludes 排除文件列表
```

- resources 属性

jar 包的资源列表，也可以使用 glob 函数获取一组资源，每个资源文件映射到 jar 包中的路径规则为：
    
resources 路径（字符串或元组）|jar 包路径
:----|:----
resources/log4j.properties|log4j.properties
src/main/resources/runtime.conf|src/main/resources/runtime.conf
('src/main/resources/runtime.conf', 'conf/runtime.conf')|conf/runtime.conf
//app/global/countries.xml|app/countries.xml

上面表格的最后一行表示非当前目录下的某个资源文件，此外也可以使用目录作为资源，目录会被展开为文件列表，每一项也遵循上述表格的映射规则

- prebuilt 属性

主要应用在已经编译打包好的 jar 包，作为一种变通的解决依赖的方式，通常对于外部依赖还是推荐使用 maven_jar 的方式。

```python
java_library(                                                                                        
    name = 'parquet-column-gdt',                                                                     
    prebuilt = True,                                                                                 
    binary_jar = 'parquet-column-1.9.1-SNAPSHOT.jar',                                                
) 
```

## maven_jar

从 maven 仓库获取第三方发布包（release/snapshot），这里的第三方是相对的概念，泛指本项目（java_library）的外部依赖

```python
maven_jar (
  name = 'hadoop-common-2.7.2-tdw',
  id = 'org.apache.hadoop:hadoop-common:2.7.2-tdw-1.0.1',  # 完整的maven artifact id
)
```

## java_fat_library
聚合所有依赖的 java_library/maven_jar，生成一个 fatjar 用于部署，类似 maven 的 jar-with-dependencies 功能

## java_binary
把java源代码编译为可执行文件

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

## java_test
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

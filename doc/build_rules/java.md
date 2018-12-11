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

### 多种依赖方式

为了适应 java 项目的需要，除了原有的 deps 依赖，新增了 exported_deps/provided_deps 依赖，这里首先需要强调的是 java_library 进行编译生成 class（jar 包）的时候**依赖不传递**，即如下 BUILD 文件中的 C.java 中定义的符号对 A.java 不可见，即在写 java_library 的 deps 时，应按需添加，与源文件中的 import 能够对应起来：deps what you imports

```python
java_library(name = 'A', srcs = 'A.java', deps = ':B')
java_library(name = 'B', srcs = 'B.java', deps = ':C')
java_library(name = 'C', srcs = 'C.java')
```

- exported_deps 属性

某些 java_library 由于接口方法的设计或者继承等原因，会自动引入定义在其他 java_library 中的符号，比如上述例子中的 B.java，如果在其某个方法的参数中引入了 C.java 定义的符号，会导致依赖 B 的 java_library 也不得不依赖 C，否则编译报错，这个时候可以将 C 作为 B 的导出依赖（exported_deps），这样依赖 B 的目标会自动传递依赖到 C

```python
java_library(name = 'B', srcs = 'B.java', exported_deps = ':C')
```

- provided_deps 属性

provided_deps 用于表示那些运行环境提供的依赖，类似 maven scope 中的 provided，这些依赖用于当前 java_library 的编译，但是当这个 java_library 直接或者间接被 java_fat_library 依赖时，provided deps 不会被打包到 fatjar 中，应用场景比如集群环境的依赖（hadoop，spark 等），可以有效减小 fatjar 的文件大小

## maven_jar

从 maven 仓库获取第三方发布包（release/snapshot），这里的第三方是相对的概念，泛指本项目（java_library）的外部依赖

```python
maven_jar (
  name = 'hadoop-common-2.7.2-tdw',
  id = 'org.apache.hadoop:hadoop-common:2.7.2-tdw-1.0.1',  # 完整的maven artifact id
)
```

除了 name 和 id 属性，maven_jar 也提供了如下属性，兼容 maven 仓库中选取依赖的多种方式

- classifier 属性

指定 classifier 值，对于同一组 id（group:artifact:version），可以用 classifier 来指定不同的 jar 包，如 hadoop-common-2.2.0.jar 和 hadoop-common-2.2.0-tests.jar

- transitive 属性

指定是否传递，默认是 True，下载 jar 包及其传递依赖，指定为 False 时表示只下载 id 对应的 standalone jar 包，不下载依赖，用于解决某些运行时依赖下载传递依赖时的失败

## java_fat_library

聚合所有依赖的 java_library/maven_jar，生成一个 fatjar 用于部署，类似 maven 的 jar-with-dependencies 功能

```python
java_library(
    name = 'log_process',
    srcs = glob(['**/*.java'], excludes = ['*Test.java']),
    resources = glob(['resources/*']),
    deps = [
        ':log_proto',
        '//log/com/tencent/monitor:monitor',
        '//log/com/tencent/monitor:schema',
        '//thirdparty/java/deps:hbase-client',
        '//thirdparty/java/deps:snappy',
    ],
    provided_deps = [
        '//thirdparty/java/deps:hadoop-common',
        '//thirdparty/java/deps:hadoop-mapreduce',
        '//thirdparty/java/deps:log4j',
        '//thirdparty/java/deps:slf4j',
    ],
)

java_fat_library(
    name = 'log_process_main',
    deps = [
        ':log_process',
        '//thirdparty/java/deps:guava',
    ],
    resources = [
        ('//log/configuration/log4j.properties', 'log4j.properties'),
        ('//log/configuration/sites.xml', 'conf/sites.xml'),
    ],
    exclusions = [
        'com.google.protobuf:*:*',
        'org.apache.spark:*:*',
    ]
)

```

- name/srcs/deps/resources 和 java_library 相同

- exclusions 属性

指定需要排除的 maven 依赖，形式为 maven id（group:artifact:version），支持通配符形式，如 com.google.protobuf:protobuf:\* 和 com.google.protobuf:\*:\*

## java_binary
把java源代码编译为可执行文件

```python
java_binary(
    name = 'poppy_java_example',
    srcs = [
        glob('src/com/soso/poppy/tool/*.Java)'
    ],
    deps = [
        '//poppy:poppy_java_client',
        '//poppy:rpc_example_proto',
    ]
)
```
编译结果包括一个启动用的shell脚本文件和一个已经包含了相关依赖的fat-jar。

## java_test
编译和运行java测试代码。
```python
java_test(
    name = 'poppy_java_test',
    srcs = [
        glob('test/com/soso/poppy/**/*Test.Java)'
    ],
    deps = [
        '//poppy:poppy_java_client',
        '//thirdparty/junit:junit',
    ]
)
```

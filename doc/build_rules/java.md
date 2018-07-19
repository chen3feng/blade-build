# 构建Java目标

## java_library

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
## maven_jar
maven_jar (
  name = 'hadoop-common-2.7.2-tdw',
  id = 'org.apache.hadoop:hadoop-common:2.7.2-tdw-1.0.1',  # 完整的maven artifact id
  transitive = False,  # 是否自动透传其依赖
)

## java_fat_binary

## java_binary
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

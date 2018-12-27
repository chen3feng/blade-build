# 构建protobuf和thrift
---

## proto_library
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

proto_library被Java目标依赖时，会自动构建Java相关的结果，Python也类似。因此同一个proto_library目标可以被多种语言所使用。

## thrift_library
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
 

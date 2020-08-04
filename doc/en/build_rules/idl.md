# Build Protobuf and Thrift #

## proto_library ##

Build protobuf targets

```python
proto_library(
    name = 'rpc_meta_info_proto',
    srcs = 'rpc_meta_info.proto',
    deps = ':rpc_option_proto',
)
```

`deps` are other proto_library which are imported.
protobuf runtime library will be depended automatically, needn't to be specified explicitly.

proto_library support generate targets for multiple target languages.

When generate for C++ code, it generate a c++ library with corresponding header files.
To include the generated header file of a proto file, you should include it with the full path from
the root of the workspace, replace the `proto` suffix into `pb.h`.
For example, the header file of `//common/base/string_test.proto` is "common/base/string_test.pb.h".

When a java targets depends on a proto_library, the java relatived code will be generated automatically,
it is also similar to other target languages，such as python. so we only need one proto_library for
multiple target languages.

If you want to generate code for specified languages unconditionly, you can use the `target_languages` argument:

```python
proto_library(
    name = 'rpc_meta_info_proto',
    srcs = 'rpc_meta_info.proto',
    deps = ':rpc_option_proto',
    target_languages = ['java', 'python'],
)
```

The `cpp` target code is always generated.

## thrift_library ##

Can be used to generate thrift C++ library
deps is the other thrift_library which are imported.
thrift runtime will be depended automatically, needn't to be specified explicitly.
The generated result is a c++ linrary with with corresponding header files.

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

Similay to proto_library, to include generated header files, the full path is also required.

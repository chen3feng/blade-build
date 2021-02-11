proto_library(
    name = 'rpc_option_proto',
    srcs = 'rpc_option.proto',
    visibility = ['PUBLIC'],
)

proto_library(
    name = 'rpc_meta_info_proto',
    srcs = 'rpc_meta_info.proto',
    deps = ':rpc_option_proto',
    visibility = ['PUBLIC'],
)

cc_library(
    name='use_protos',
    srcs=['use_protos.cpp'],
    hdrs=[],
    deps=[
         ':rpc_meta_info_proto',
         ':rpc_option_proto'
    ],
    visibility = ['PUBLIC'],
)

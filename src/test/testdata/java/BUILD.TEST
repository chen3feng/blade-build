java_library(
    name = 'poppy_java_client',
    srcs = glob('src/com/soso/poppy/**/*.java', exclude=['*Main.java']),
    deps = [
        '//proto:rpc_meta_info_proto',
        '//proto:rpc_option_proto',
        '//java/lib:junit'
    ]
)

"""
java_binary(
    name = 'hello_main',
    srcs = ['src/com/soso/poppy/HelloMain.java'],
    deps = [
        ':poppy_java_client',
    ],
    main_class = 'HelloMain',
)
"""

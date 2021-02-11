cc_library(
    name = 'lib1',
    srcs = [
        'lib1.cc',
        'lib1_impl.h',
    ],
    hdrs = ['lib1.h'],
)

cc_library(
    name = 'lib2',
    srcs = [
        'lib2.cc',
        'lib2_impl.h',
    ],
    hdrs = ['lib2.h'],
    deps = [':lib1'],
)

cc_binary(
    name = 'exe',
    srcs = [
        'exe.cc',
        'exe.h',
    ],
    deps = [
        ':lib2'
    ],
)

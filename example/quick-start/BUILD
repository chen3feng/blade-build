cc_library(
    name = 'say',
    hdrs = ['say.h'],
    srcs = ['say.cpp'],
)

cc_library(
    name = 'hello',
    hdrs = ['hello.h'],
    srcs = ['hello.cpp'],
    deps = [':say'],
)

cc_binary(
    name = 'hello-world',
    srcs = ['hello-world.cpp'],
    deps = [':hello'],
)

cc_library(
    name = 'template_cpu',
    srcs = ['template_cpu.cpp'],
    hdrs = [],
)

cu_library(
    name = 'util',
    srcs = ['util.cc'],
    # cuda_path = '//thirdparty/cuda/11.2',
    hdrs = ['util.h'],
    deps = [],
    extra_cppflags = [
        '-D_TEST_CPP_FLAG=1',
    ],
    extra_cuflags = [
        '-gencode=arch=compute_75,code=sm_75',
    ],
)

cu_binary(
    name = 'template',
    srcs = ['template.cu'],
    # cuda_path = '//thirdparty/cuda/11.2',
    deps = [
        ':template_cpu',
        ':util',
    ],
    extra_cppflags = [
        '-std=c++17',
    ],
)

cu_test(
    name = 'cu_test',
    # cuda_path = '//thirdparty/cuda/11.2',
    srcs = ['cu_test.cu'],
    deps = [':template_cpu', ':util'],
    extra_cppflags = [
        '-std=c++17',
    ],
)

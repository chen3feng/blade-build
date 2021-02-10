cc_library(
    name = 'extra',
    srcs = ['extra.cpp'],
    hdrs = ['extra.h'],
    export_incs = [
        'include'
    ],
    deps = [
        ':extra_extra',
        '//common:common',
    ]
)

cc_library(
    name = 'extra_extra',
    srcs = 'extra_extra.cpp',
    hdrs = [],
    export_incs = [
        './extra'
    ]
)

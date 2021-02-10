gen_rule(
    name = 'gen_header',
    outs = 'header.h',
    cmd = 'touch $FIRST_OUT; echo $FIRST_OUT',
)

cc_binary(
    name = 'binary',
    srcs = 'main.cpp',
    deps = ':gen_header',
)

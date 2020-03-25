lex_yacc_library(
    name = 'example_llyy',
    srcs = ['example.ll', 'example.yy'],
    lexflags = ['--debug'],
    yaccflags = ['--debug'],
)

cc_binary(
    name = 'example',
    srcs = 'example.cpp',
    deps = ':example_llyy',
)

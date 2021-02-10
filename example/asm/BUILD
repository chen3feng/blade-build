cc_library(
    name = 'asm',
    srcs = [enable_if(build_target.bits==32, 'asm32.s', 'asm64.s'), 'asm.S'],
    hdrs = [],
)

cc_binary(
    name = 'asm_test',
    srcs = 'asm_test.c',
    deps = ':asm'
)

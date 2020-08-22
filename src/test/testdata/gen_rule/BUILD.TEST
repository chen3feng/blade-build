gen_rule(
    name='process_media',
    outs='process.tmp',
    cmd='echo this_is_the_process_gen_rule > $FIRST_OUT',
    deps=['//cc:lowercase']
)

cc_library(
    name='use_media',
    srcs=['use_media.cpp'],
    hdrs=['use_media.h'],
    deps=[
        ':process_media'
    ]
)

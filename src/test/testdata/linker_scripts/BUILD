cc_plugin(
    name = 'hw',
    srcs = ['hello.c', 'world.c'],
    version_scripts = 'hw.map',
)

cc_binary(
    name = 'main',
    srcs = ['hello.c', 'world.c', 'main.c'],
    version_scripts = ['hw.map'],
)

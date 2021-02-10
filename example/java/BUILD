java_library(
    name = 'foo',
    srcs = glob('foo/src/main/java/**/*.java'),
)

java_binary(
    name = 'bar',
    srcs = glob('bar/src/main/java/**/*.java'),
    deps = ':foo',
    main_class = 'org.blade.foo.Bar',
)

java_test(
    name = 'foo_test',
    srcs = glob('foo/src/test/java/**/*.java'),
    deps = ':foo'
)

java_test(
    name = 'bar_test',
    srcs = glob('bar/src/test/java/**/*.java'),
    deps = ':bar'
)

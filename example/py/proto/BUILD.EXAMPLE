proto_library(
    name = 'address_book_proto',
    srcs = [
        'address_book.proto',
        'person.proto'
    ]
)

proto_library(
    name = 'echo_proto',
    srcs = 'echo.proto',
    deps = ':address_book_proto'
)


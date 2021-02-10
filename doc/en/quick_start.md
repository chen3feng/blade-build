# Quick Start

Let's start with a hello-world to practice using Blade.

## Create a workspace

```console
$ mkdir quick-start
$ cd quick-start
$ touch BLADE_ROOT
```

## Define and implement the `say` library

Create the header file `say.h`:

```cpp
#pragma once
#include <string>

// Say a message
void Say(const std::string& msg);
```

Create the implementation file `say.cpp`:

```cpp
#include "say.h"
#include <iostream>

void Say(const std::string& msg) {
    std::cout << msg << "!\n";
}
```

Create a `BUILD` file and describe the above file as a `say` library:

```python
cc_library(
    name ='say',
    hdrs = ['say.h'],
    srcs = ['say.cpp'],
)
```

`cc_library` means that this is a C/C++ library, `hdrs` means the library’s public interface header files, and `srcs` means its
implementation files. If there are private header files, also put them in `srcs`.

## Define and implement the hello library

Create the header file `hello.h`:

```cpp
#pragma once
#include <string>

// Say hello to `to`
void Hello(const std::string& to);
```

Create the implementation file `hello.cpp`:

```cpp
#include "say.h"

void Hello(const std::string& to) {
    Say("Hello, "+ to);
}
```

Create a `BUILD` file and describe the above file as a `hello` library:

```python
cc_library(
    name ='hello',
    hdrs = ['hello.h'],
    srcs = ['hello.cpp'],
    deps = [':say'],
)
```

It looks similar to the say library, but with an additional `deps` parameter, which means it depends
on the `say` library. The `:` prefix indicates that the target is in the same `BUILD` file.

## Implement the `hello-world` program

Create the `hello-world.c` file:

```c
#include "hello.h"

int main() {
    Hello("World");
    return 0;
}
```

Add the rule call for compiling `hello-world` in the `BUILD` file:

```python
cc_binary(
    name ='hello-world',
    srcs = ['hello-world.c'],
    deps = [':hello'],
)
```

Note that the rule name is `cc_binary`, the dependency on the `hello` library needs to be added to the `deps`, but there is no
need to add the dependency on the `say` library, because this is the implementation details of `hello`, the `hello-world` target
does not need to be understood. When compiling and linking, Blade will correctly handle the transfer of dependencies.

Build the `hello-world` program:

```console
$ blade build :hello-world
Blade(info): Building...
Blade(info): Build success.
```

Run the `hello-world` program:

```console
$ blade run :hello-world
Blade(info): Building...
Blade(info): Build success.
Blade(info): Run'['/data1/code/blade-build/example/quick-start/build64_release/hello-world']'
Hello, World!
```

For a complete example, see [quick-start](../../example/quick-start) under [example](../../example).

#include "foo/foo.h"

#include <iostream>
#include "common/common.h"

void Foo()
{
    Common();
    std::cout << "Foo" << "\n";
}

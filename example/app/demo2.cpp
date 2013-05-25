#include <pthread.h>
#include "bar/bar.h"
#include "extra.h"
#include "foo/foo.h"

int main()
{
    Foo();
    Bar();
    Extra();
    pthread_setconcurrency(10);
}

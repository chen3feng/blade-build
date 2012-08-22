#include <pthread.h>
#include "foo/foo.h"
#include "bar/bar.h"

int main()
{
    Foo();
    Bar();
    pthread_setconcurrency(10);
}

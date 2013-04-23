#include <pthread.h>
#include "bar/bar.h"
#include "extra.h"
#include "foo/foo.h"

int main()
{
    Bar();
    Extra();
    Foo();
    pthread_setconcurrency(10);
}

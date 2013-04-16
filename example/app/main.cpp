#include <pthread.h>
#include "foo.h"

int main()
{
    Foo();
    pthread_setconcurrency(10);
}

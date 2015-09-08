package org.blade.foo;

import org.junit.Test;
import static org.junit.Assert.*;

public class FooTest {
    @Test
    public void testFoo() {
        Foo foo = new Foo();
        int a = 1;
        int b = 1;
        assertEquals(a, b);
    }
}

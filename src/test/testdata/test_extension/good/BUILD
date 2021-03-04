load('extension.bld', 'VAR1')
assert VAR1 == 1

try:
    VAR2
except NameError:
    pass

load('extension.bld', 'VAR1', VAR2_ALIAS='VAR2')

assert VAR2_ALIAS == 2

include('extension.bld')

assert VAR2 == 2
assert VAR2_ALIAS == VAR2
assert VAR3 == 3

load('extension.bld', 'HAS_NATIVE')
assert HAS_NATIVE

include('extension.bld')
assert not HAS_NATIVE


try:
    native.cc_library
    assert True
except NameError:
    pass

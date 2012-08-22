"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the Namespace module which provides Namespace utility.

"""


__all__ = ("Namespace", "as_namespace")


from collections import Mapping, Sequence


class _Dummy(object):
    def __init__(self):
        pass

CLASS_ATTRS = dir(_Dummy)
del _Dummy


class Namespace(dict):
    """A dict subclass that exposes its items as attributes.

    Warning: Namespace instances do not have direct access to the
    dict methods.

    """
    def __init__(self, obj={}):
        super(Namespace, self).__init__(obj)

    def __dir__(self):
        return tuple(self)

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__, super(self).__repr__())

    def __getattribute__(self, name):
        try:
            return self[name]
        except KeyError:
            msg = "'%s' object has no attribute '%s'"
            raise AttributeError(msg % (type(self).__name__, name))

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        del self[name]

    @classmethod
    def from_object(cls, obj, names=None):
        """Copy constructors"""
        if names is None:
            names = dir(obj)
        ns = {name:getattr(obj, name) for name in names}
        return cls(ns)

    @classmethod
    def from_mapping(cls, ns, names=None):
        """Copy from mapping"""
        if names:
            ns = {name:ns[name] for name in names}
        return cls(ns)

    @classmethod
    def from_sequence(cls, seq, names=None):
        """Copy from sequence """
        if names:
            seq = {name:val for name, val in seq if name in names}
        return cls(seq)

    @staticmethod
    def hasattr(ns, name):
        try:
            object.__getattribute__(ns, name)
        except AttributeError:
            return False
        return True

    @staticmethod
    def getattr(ns, name):
        return object.__getattribute__(ns, name)

    @staticmethod
    def setattr(ns, name, value):
        return object.__setattr__(ns, name, value)

    @staticmethod
    def delattr(ns, name):
        return object.__delattr__(ns, name)


def as_namespace(obj, names=None):

    if isinstance(obj, type(as_namespace)):
        obj = obj()

    if isinstance(obj, type):
        names = (name for name in dir(obj) if name not in CLASS_ATTRS)
        return Namespace.from_object(obj, names)
    if isinstance(obj, Mapping):
        return Namespace.from_mapping(obj, names)
    if isinstance(obj, Sequence):
        return Namespace.from_sequence(obj, names)

    return Namespace.from_object(obj, names)

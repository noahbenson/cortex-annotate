# -*- coding: utf-8 -*-
################################################################################
# annotate/_util.py
#
# Utility types and functions used in the annotation toolkit.


# Dependencies #################################################################

from functools import partial


# Lazy Dict Type ###############################################################
# The Lazy Dict type (ldict) is a mutable dictionary whose values may be delay
# objects (also defined here). Delay objects are automatically undelayed before
# they are revealed to the user.
# These ldict objects probably don't behave correctly with respect to dictionary
# equality, but that is a fairly small issue for a mutable dictionary.

class delay:
    """A delayed computation type.
    
    A `delay` object can be initialized exactly like a `partial` object (from
    the `functools` package) except that all of the arguments to the delayed
    function must be provided at initialization, unlike with a `partial`. The
    computation can be run and its result accessed by calling the `delay` object
    without arguments.
    
    Unlike a `partial` object, a `delay` object saves its result after it has
    been computed once and does not recall (or even keey a reference to) the
    original function after this point.
    """
    __slots__ = ('_partial', '_result')
    def __setattr__(self, k, v):
        raise TypeError(f"{type(self)} is immutable")
    def __call__(self):
        if self._partial is not None:
            object.__setattr__(self, '_result', self._partial())
            object.__setattr__(self, '_partial', None)
        return self._result
    def __init__(self, f, *args, **kw):
        object.__setattr__(self, '_partial', partial(f, *args, **kw))
        object.__setattr__(self, '_result', None)
    @property
    def is_cached(self):
        "Returns `True` if the delay object has been cached, otherwise `False`."
        return (self._partial is None)
def undelay(obj):
    """Returns the argument except for delays whose result values are returned.
    
    `undelay(d)` for a `delay` object `d` returns `d()`.
    
    `undelay(x)` for any object `x` that is not a `delay` object returns `x`.
    """
    return obj() if type(obj) is delay else obj
class ldict_setlike:
    __slots__ = ('_setlike',)
    @classmethod
    def _undelay(cls, ld):
        raise TypeError(f'{cls} has no _undelay method')
    @classmethod
    def _to_setlike(cls):
        raise TypeError(f'{cls} has no _to_setlike method')
    def __setattr__(self, k, v):
        raise TypeError(f"{type(self)} is immutable")
    def __getitem__(self, k):
        raise TypeError(f"{type(self)} is not subscriptable") 
    def __init__(self, ld):
        object.__setattr__(self, '_setlike', self._to_setlike(ld))
    def __iter__(self):
        return map(self._undelay, iter(self._setlike))
    def __reversed__(self, k):
        return map(self._undelay, reversed(self._setlike))
    def __len__(self):
        return len(self._setlike)
    def __contains__(self, k):
        return (k in self._setlike) or (k in iter(self))
    def __eq__(self, other):
        if type(self) is not type(other): return False
        if len(self) != len(other): return False
        return all(x in other for x in iter(self))
class ldict_items(ldict_setlike):
    @classmethod
    def _undelay(cls, el):
        return (el[0], undelay(el[1]))
    @classmethod
    def _to_setlike(cls, ld):
        return dict.items(ld)
    __slots__ = ()
class ldict_values(ldict_setlike):
    @classmethod
    def _undelay(cls, el):
        return undelay(el)
    @classmethod
    def _to_setlike(cls, ld):
        return dict.values(ld)
    __slots__ = ()
class ldict(dict):
    """A lazy dictionary type.
    
    `ldict` is identical to `dict` except that it calls `undelay` on all values
    before returning them, so it can be used to store lazy computations.
    """
    __slots__ = ()
    def __getitem__(self, k):
        v = dict.__getitem__(self, k)
        return undelay(v)
    def items(self):
        return ldict_items(self)
    def values(self):
        return ldict_values(self)
    def __eq__(self, other):
        if not isinstance(other, dict): return False
        if len(self) != len(other): return False
        if self.keys() != other.keys(): return False
        other_items = other.items()
        self_items = ldict_items(self)
        return all(kv in other_items for kv in self_items)
    def is_lazy(self, k):
        """Returns `True` if the given key is an uncached lazy value."""
        v = dict.__getitem__(self, k)
        return (not v.is_cached) if type(v) is delay else False

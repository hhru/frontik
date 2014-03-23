# -*- coding: utf-8 -*-
import collections


class FrozenDict(collections.Mapping):
    """Frozen dict for using nested structures as keys in dicts.
    Attribute goes to Mike Graham http://stackoverflow.com/questions/2703599/what-would-be-a-frozen-dict"""

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __hash__(self):
        if self._hash is None:
            self._hash = 0
            for pair in self.iteritems():
                self._hash ^= hash(pair)
        return self._hash

    def __str__(self):
        return "frozen " + str(self._d)

    def __unicode__(self):
        return u"frozen " + unicode(self._d)

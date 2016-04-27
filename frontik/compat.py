# coding=utf-8

import sys

PY3 = sys.version_info >= (3,)

if PY3:
    def iteritems(d, **kw):
        return d.items(**kw)

else:
    def iteritems(d, **kw):
        return d.iteritems(**kw)

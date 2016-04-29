# coding=utf-8

import sys

PY3 = sys.version_info >= (3,)

if PY3:
    import urllib.parse as urlparse_alias

    def iteritems(d, **kw):
        return d.items(**kw)

else:
    import urlparse as urlparse_alias

    def iteritems(d, **kw):
        return d.iteritems(**kw)

urlparse = urlparse_alias

# coding=utf-8

import sys

__all__ = [
    'basestring_type', 'iteritems', 'long_type', 'SimpleCookie', 'unicode_type',
    'urlencode', 'urlparse', 'httplib', 'quote', 'unquote_plus'
]

PY3 = sys.version_info >= (3,)

if PY3:
    import urllib.parse as urlparse
    from urllib.parse import urlencode
    import http.client as httplib
    from urllib.parse import quote, unquote_plus

    basestring_type = str
    long_type = int
    unicode_type = str

    def iteritems(d, **kw):
        return d.items(**kw)

else:
    from urllib import urlencode
    import urlparse
    import httplib
    from urllib import quote, unquote_plus

    basestring_type = basestring
    long_type = long
    unicode_type = unicode

    def iteritems(d, **kw):
        return d.iteritems(**kw)

try:
    from tornado.httputil import SimpleCookie  # Tornado with patched cookies (https://github.com/hhru/tornado)
except ImportError:
    if PY3:
        from http.cookies import SimpleCookie
    else:
        from Cookie import SimpleCookie

# coding=utf-8

import sys

__all__ = ['iteritems', 'SimpleCookie', 'unquote_plus', 'urlencode', 'urlparse']

PY3 = sys.version_info >= (3,)

if PY3:
    import urllib.parse as urlparse
    from urllib.parse import unquote_plus
    from urllib.parse import urlencode

    def iteritems(d, **kw):
        return d.items(**kw)

else:
    from urllib import unquote_plus
    from urllib import urlencode
    import urlparse

    def iteritems(d, **kw):
        return d.iteritems(**kw)

try:
    from tornado.httputil import SimpleCookie  # Tornado with patched cookies (https://github.com/hhru/tornado)
except ImportError:
    if PY3:
        from http.cookies import SimpleCookie
    else:
        from Cookie import SimpleCookie

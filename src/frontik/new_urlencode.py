# got from http://bugs.python.org/file13294/new_urlencode.py

from urllib import quote_plus
import sys


def urlencode(query, doseq=0, safe='', encoding=None, errors=None):
    """Encode a sequence of two-element tuples or dictionary into a URL query string.

    If any values in the query arg are sequences and doseq is true, each
    sequence element is converted to a separate parameter.

    If the query arg is a sequence of two-element tuples, the order of the
    parameters in the output will match the order of parameters in the
    input.

    >>> urlencode((("\\u00a0","\\u00c1"), (b'\\xa0\\x24', b'\\xc1\\x24'), 
    ... (1, 2), ("a:", "b$")))
    '%C2%A0=%C3%81&%A0%24=%C1%24&1=2&a%3A=b%24'
    >>> urlencode((("\\u00a0","\\u00c1"), (b'\\xa0\\x24', b'\\xc1\\x24'), 
    ... (1, 2), ("a:", "b$")), safe=":$")
    '%C2%A0=%C3%81&%A0$=%C1$&1=2&a:=b$'
    >>> urlencode((("\\u00a0","\\u00c1"), (b'\\xa0\\x24', b'\\xc1\\x24'), 
    ... (1, 2), ("a:", "b$")), encoding="latin=1")
    '%A0=%C1&%A0%24=%C1%24&1=2&a%3A=b%24'
    >>> urlencode((("\\u00a0","\\u00c1"), (b'\\xa0\\x24', b'\\xc1\\x24'), 
    ... (1, 2), ("a:", "b$")), safe="$:", encoding="latin=1")
    '%A0=%C1&%A0$=%C1$&1=2&a:=b$'

    >>> urlencode((("\\u00a0","\\u00c1"), (b'\\xa0\\x24', b'\\xc1\\x24'), 
    ... ("d:", 0xe), (1, ("b", b'\\x0c\\x24', 0xd, "e$"))), 1)
    '%C2%A0=%C3%81&%A0%24=%C1%24&d%3A=14&1=b&1=%0C%24&1=13&1=e%24'
    >>> urlencode((("\\u00a0","\\u00c1"), (b'\\xa0\\x24', b'\\xc1\\x24'), 
    ... ("d:", 0xe), (1, ("b", b'\\x0c\\x24', 0xd, "e$"))), 1, safe=":$")
    '%C2%A0=%C3%81&%A0$=%C1$&d:=14&1=b&1=%0C$&1=13&1=e$'
    >>> urlencode((("\\u00a0","\\u00c1"), (b'\\xa0\\x24', b'\\xc1\\x24'), 
    ... ("d:", 0xe), (1, ("b", b'\\x0c\\x24', 0xd, "e$"))), 1, encoding="latin-1")
    '%A0=%C1&%A0%24=%C1%24&d%3A=14&1=b&1=%0C%24&1=13&1=e%24'
    >>> urlencode((("\\u00a0","\\u00c1"), (b'\\xa0\\x24', b'\\xc1\\x24'), 
    ... ("d:", 0xe), (1, ("b", b'\\x0c\\x24', 0xd, "e$"))), 1, safe=":$", encoding="latin-1")
    '%A0=%C1&%A0$=%C1$&d:=14&1=b&1=%0C$&1=13&1=e$'

    >>> urlencode((("\\u00a0", "\\u00c1"),), encoding="ASCII", errors="replace")
    '%3F=%3F'
    >>> urlencode((("\\u00a0", (1, "\\u00c1")),), 1, encoding="ASCII", errors="replace")
    '%3F=1&%3F=%3F'

    """

    if hasattr(query,"items"):
        # mapping objects
        query = query.items()
    else:
        # it's a bother at times that strings and string-like objects are
        # sequences...
        try:
            # non-sequence items should not work with len()
            # non-empty strings will fail this
            if len(query) and not isinstance(query[0], tuple):
                raise TypeError
            # zero-length sequences of all types will get here and succeed,
            # but that's a minor nit - since the original implementation
            # allowed empty dicts that type of behavior probably should be
            # preserved for consistency
        except TypeError:
            ty,va,tb = sys.exc_info()
            raise TypeError("not a valid non-string sequence or mapping object").with_traceback(tb)

    l = []
    if not doseq:
        # preserve old behavior
        for k, v in query:
            if isinstance(k, bytes):
                k = quote_plus(k, safe)
            else:
                k = quote_plus(str(k), safe, encoding, errors)

            if isinstance(v, bytes):
                v = quote_plus(v, safe)
            else: 
                v = quote_plus(str(v), safe, encoding, errors)

            l.append(k + '=' + v)
    else:
        for k, v in query:
            if isinstance(k, bytes):
                k = quote_plus(k, safe)
            else:
                k = quote_plus(str(k), safe, encoding, errors)

            if isinstance(v, str):
                v = quote_plus(v, safe, encoding, errors)
                l.append(k + '=' + v)
            elif isinstance(v, bytes):
                v = quote_plus(v, safe)
                l.append(k + '=' + v)
            else:
                try:
                    # is this a sufficient test for sequence-ness?
                    x = len(v)
                except TypeError:
                    # not a sequence
                    v = quote_plus(str(v), safe, encoding, errors)
                    l.append(k + '=' + v)
                else:
                    # loop over the sequence
                    for elt in v:
                        if isinstance(elt, bytes):
                            elt = quote_plus(elt, safe)
                        else:
                            elt = quote_plus(str(elt), safe, encoding, errors)
                        l.append(k + '=' + elt)
    return '&'.join(l)

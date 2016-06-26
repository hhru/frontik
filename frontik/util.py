# coding=utf-8

import mimetypes
import re
from uuid import uuid4

from tornado.escape import to_unicode, utf8
from tornado.httpclient import HTTPRequest
from tornado.httputil import HTTPHeaders

from frontik.compat import iteritems, unicode_type, urlencode, urlparse


def list_unique(l):
    return list(set(l))


def any_to_unicode(s):
    if isinstance(s, bytes):
        return to_unicode(s)

    return unicode_type(s)


def any_to_bytes(s):
    if isinstance(s, unicode_type):
        return utf8(s)
    elif isinstance(s, bytes):
        return s

    return utf8(str(s))


def _encode(s):
    if isinstance(s, unicode_type):
        return utf8(s)

    return s


def make_qs(query_args):
    kv_pairs = []
    for key, val in iteritems(query_args):
        if val is not None:
            encoded_key = _encode(key)
            if isinstance(val, (set, frozenset, list, tuple)):
                for v in val:
                    kv_pairs.append((encoded_key, _encode(v)))
            else:
                kv_pairs.append((encoded_key, _encode(val)))

    return urlencode(kv_pairs)


def make_body(data):
    return make_qs(data) if isinstance(data, dict) else data


def make_url(base, **query_args):
    """
    Builds URL from base part and query arguments passed as kwargs.
    Returns unicode string
    """
    qs = make_qs(query_args)

    if qs:
        return to_unicode(base) + ('&' if '?' in base else '?') + qs
    else:
        return to_unicode(base)


def decode_string_from_charset(string, charsets=('cp1251',)):
    if isinstance(string, unicode_type):
        return string

    decoded_body = None
    for c in charsets:
        try:
            decoded_body = string.decode(c)
            break
        except UnicodeError:
            continue

    if decoded_body is None:
        raise UnicodeError('Could not decode string (tried: {0})'.format(', '.join(charsets)))

    return decoded_body


def get_query_parameters(url):
    url = 'http://' + url if not re.match(r'[a-z]+://.+\??.*', url, re.IGNORECASE) else url
    return urlparse.parse_qs(urlparse.urlparse(url).query, True)


def choose_boundary():
    """
    Our embarassingly-simple replacement for mimetools.choose_boundary.
    See https://github.com/kennethreitz/requests/blob/master/requests/packages/urllib3/filepost.py
    """
    return _encode(uuid4().hex)

BOUNDARY = choose_boundary()


def make_mfd(fields, files):
    """
    Constructs request body in multipart/form-data format

    fields :: { field_name : field_value }
    files :: { field_name: [{ "filename" : fn, "body" : bytes }]}
    """

    def create_field(name, data):
        return [
            b'--', BOUNDARY,
            b'\r\nContent-Disposition: form-data; name="', any_to_bytes(name),
            b'"\r\n\r\n', any_to_bytes(data), b'\r\n'
        ]

    def create_file_field(name, filename, data):
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        return [
            b'--', BOUNDARY,
            b'\r\nContent-Disposition: form-data; name="', any_to_bytes(name),
            b'"; filename="', any_to_bytes(filename),
            b'"\r\nContent-Type: ', any_to_bytes(content_type),
            b'\r\n\r\n', any_to_bytes(data), b'\r\n'
        ]

    body = []

    for name, data in iteritems(fields):
        if data is None:
            continue

        if isinstance(data, list):
            for value in data:
                if value is not None:
                    body.extend(create_field(name, value))
        else:
            body.extend(create_field(name, data))

    for name, files in iteritems(files):
        for file in files:
            body.extend(create_file_field(name, file['filename'], file['body']))

    body.extend([b'--', BOUNDARY, b'--\r\n'])
    content_type = b'multipart/form-data; boundary=' + BOUNDARY

    return b''.join(body), content_type


def make_get_request(url, data=None, headers=None, connect_timeout=None, request_timeout=None, follow_redirects=True):
    data = {} if data is None else data
    headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)

    return HTTPRequest(
        url=make_url(url, **data),
        follow_redirects=follow_redirects,
        headers=headers,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout
    )


def make_post_request(url, data='', headers=None, files=None, content_type=None,
                      connect_timeout=None, request_timeout=None, follow_redirects=True):
    if files:
        body, content_type = make_mfd(data, files)
    else:
        body = make_body(data)

    headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)
    if content_type is None:
        content_type = headers.get('Content-Type', 'application/x-www-form-urlencoded')

    headers.update({'Content-Type': content_type, 'Content-Length': str(len(body))})

    return HTTPRequest(
        url=url,
        body=body,
        method='POST',
        headers=headers,
        follow_redirects=follow_redirects,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout
    )


def make_put_request(url, data='', headers=None, content_type=None, connect_timeout=None, request_timeout=None):
    headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)
    if content_type is not None:
        headers['Content-Type'] = content_type

    return HTTPRequest(
        url=url,
        body=make_body(data),
        method='PUT',
        headers=headers,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout
    )


def make_delete_request(url, data=None, headers=None, content_type=None, connect_timeout=None, request_timeout=None):
    data = {} if data is None else data
    headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)
    if content_type is not None:
        headers['Content-Type'] = content_type

    return HTTPRequest(
        url=make_url(url, **data),
        method='DELETE',
        headers=headers,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout
    )


def make_head_request(url, data=None, headers=None, connect_timeout=None, request_timeout=None, follow_redirects=True):
    data = {} if data is None else data
    headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)

    return HTTPRequest(
        url=make_url(url, **data),
        follow_redirects=follow_redirects,
        method='HEAD',
        headers=headers,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout
    )


def _asciify_url_char(c):
    if ord(c) > 127:
        return hex(ord(c)).replace('0x', '%')
    else:
        return c


def asciify_url(url):
    return ''.join(map(_asciify_url_char, url))


def get_cookie_or_url_param_value(handler, param_name):
    return handler.get_argument(param_name, handler.get_cookie(param_name, None))

# coding=utf-8

import mimetools
import mimetypes
import re
import urlparse
from urllib import urlencode

from tornado.httpclient import HTTPRequest
from tornado.httputil import HTTPHeaders


def list_unique(l):
    return list(set(l))


def _encode(s):
    if isinstance(s, unicode):
        return s.encode('utf-8')
    else:
        return s


def make_qs(query_args):
    kv_pairs = []
    for key, val in query_args.iteritems():
        if val is not None:
            encoded_key = _encode(key)
            if isinstance(val, (set, frozenset, list, tuple)):
                for v in val:
                    kv_pairs.append((encoded_key, _encode(v)))
            else:
                kv_pairs.append((encoded_key, _encode(val)))

    qs = urlencode(kv_pairs)

    return qs


def make_body(data):
    return make_qs(data) if isinstance(data, dict) else data


def make_url(base, **query_args):
    """
    построить URL из базового урла и набора CGI-параметров
    параметры с пустым значением пропускаются, удобно для последовательности:
    make_url(base, hhtoken=request.cookies.get('hhtoken'))
    """
    qs = make_qs(query_args)

    if qs:
        return base + ('&' if '?' in base else '?') + qs
    else:
        return base


def decode_string_from_charset(string, charsets=('cp1251',)):
    if isinstance(string, unicode):
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


BOUNDARY = mimetools.choose_boundary()
ENCODE_TEMPLATE = '--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{data}\r\n'
ENCODE_TEMPLATE_FILE = ('--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                        'filename="{filename}"\r\nContent-Type: {contenttype}\r\n\r\n{data}\r\n')


def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'


def make_mfd(fields, files):
    """
    Constructs request body in multipart/form-data format

    fields :: { field_name : field_value }
    files :: { field_name: [{ "filename" : fn, "body" : bytes }]}
    """

    body = ""

    for name, data in fields.iteritems():

        if data is None:
            continue

        if isinstance(data, list):
            for value in data:
                if data is None:
                    continue
                body += ENCODE_TEMPLATE.format(
                    boundary=BOUNDARY,
                    name=str(name),
                    data=_encode(value)
                )
        else:
            body += ENCODE_TEMPLATE.format(
                boundary=BOUNDARY,
                name=str(name),
                data=_encode(data)
            )

    for name, files in files.iteritems():
        for file in files:
            body += ENCODE_TEMPLATE_FILE.format(
                boundary=BOUNDARY,
                data=_encode(file["body"]),
                name=name,
                filename=_encode(file["filename"]),
                contenttype=get_content_type(file["filename"])
            )

    body += '--%s--\r\n' % BOUNDARY
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return body, content_type


def make_get_request(url, data=None, headers=None, connect_timeout=None, request_timeout=None, follow_redirects=True):
    data = {} if data is None else data
    headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)

    return HTTPRequest(
        url=_encode(make_url(url, **data)),
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
        url=_encode(url),
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
        url=_encode(url),
        body=make_body(data),
        method='PUT',
        headers=headers,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout
    )


def make_delete_request(url, data='', headers=None, content_type=None, connect_timeout=None, request_timeout=None):
    headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)
    if content_type is not None:
        headers['Content-Type'] = content_type

    return HTTPRequest(
        url=_encode(url),
        body=make_body(data),
        method='DELETE',
        headers=headers,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout
    )


def make_head_request(url, data=None, headers=None, connect_timeout=None, request_timeout=None, follow_redirects=True):
    data = {} if data is None else data
    headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)

    return HTTPRequest(
        url=_encode(make_url(url, **data)),
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

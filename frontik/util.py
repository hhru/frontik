# coding=utf-8

import mimetypes
import os.path
import re
from uuid import uuid4

from tornado.concurrent import Future
from tornado.escape import to_unicode, utf8
from tornado.util import raise_exc_info

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
    def addslashes(text):
        for s in (b'\\', b'"'):
            if s in text:
                text = text.replace(s, b'\\' + s)
        return text

    def create_field(name, data):
        name = addslashes(any_to_bytes(name))

        return [
            b'--', BOUNDARY,
            b'\r\nContent-Disposition: form-data; name="', name,
            b'"\r\n\r\n', any_to_bytes(data), b'\r\n'
        ]

    def create_file_field(name, filename, data, content_type):
        if content_type == 'application/unknown':
            content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        else:
            content_type = content_type.replace('\n', ' ').replace('\r', ' ')

        name = addslashes(any_to_bytes(name))
        filename = addslashes(any_to_bytes(filename))

        return [
            b'--', BOUNDARY,
            b'\r\nContent-Disposition: form-data; name="', name, b'"; filename="', filename,
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
            body.extend(create_file_field(
                name, file['filename'], file['body'], file.get('content_type', 'application/unknown')
            ))

    body.extend([b'--', BOUNDARY, b'--\r\n'])
    content_type = b'multipart/form-data; boundary=' + BOUNDARY

    return b''.join(body), content_type


def get_cookie_or_url_param_value(handler, param_name):
    return handler.get_argument(param_name, handler.get_cookie(param_name, None))


def reverse_regex_named_groups(pattern, *args, **kwargs):
    class GroupReplacer(object):
        def __init__(self, args, kwargs):
            self.args, self.kwargs = args, kwargs
            self.current_arg = 0

        def __call__(self, match):
            value = ''
            named_group = re.search(r'^\?P<(\w+)>(.*?)$', match.group(1))

            if named_group:
                group_name = named_group.group(1)
                if group_name in self.kwargs:
                    value = self.kwargs[group_name]
                elif self.current_arg < len(self.args):
                    value = self.args[self.current_arg]
                    self.current_arg += 1
                else:
                    raise ValueError('Cannot reverse regex: required number of arguments not found')

            return any_to_unicode(value)

    result = re.sub(r'\(([^)]+)\)', GroupReplacer(args, kwargs), to_unicode(pattern))
    return result.replace('^', '').replace('$', '')


def raise_future_exception(future):
    exception = future.exception()

    if isinstance(future, Future):
        raise_exc_info(future.exc_info())
    elif hasattr(future, 'exception_info') and future.exception_info()[1] is not None:
        raise_exc_info((type(exception),) + future.exception_info())
    else:
        raise exception


def get_abs_path(root_path, relative_path):
    if relative_path is None or os.path.isabs(relative_path):
        return relative_path

    return os.path.normpath(os.path.join(root_path, relative_path))

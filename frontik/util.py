import asyncio
import datetime
import logging
import os.path
import random
import re
from urllib.parse import urlencode
from uuid import uuid4

from tornado.escape import to_unicode, utf8


logger = logging.getLogger('util')


def any_to_unicode(s):
    if isinstance(s, bytes):
        return to_unicode(s)

    return str(s)


def any_to_bytes(s):
    if isinstance(s, str):
        return utf8(s)
    elif isinstance(s, bytes):
        return s

    return utf8(str(s))


def make_qs(query_args):
    return urlencode([(k, v) for k, v in query_args.items() if v is not None], doseq=True)


def make_body(data):
    return make_qs(data) if isinstance(data, dict) else any_to_bytes(data)


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
    if isinstance(string, str):
        return string

    decoded_body = None
    for c in charsets:
        try:
            decoded_body = string.decode(c)
            break
        except UnicodeError:
            continue

    if decoded_body is None:
        raise UnicodeError('Could not decode string (tried: {})'.format(', '.join(charsets)))

    return decoded_body


def choose_boundary():
    """
    Our embarassingly-simple replacement for mimetools.choose_boundary.
    See https://github.com/kennethreitz/requests/blob/master/requests/packages/urllib3/filepost.py
    """
    return utf8(uuid4().hex)


def get_cookie_or_url_param_value(handler, param_name):
    return handler.get_argument(param_name, handler.get_cookie(param_name, None))


def reverse_regex_named_groups(pattern, *args, **kwargs):
    class GroupReplacer:
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


def get_abs_path(root_path, relative_path):
    if relative_path is None or os.path.isabs(relative_path):
        return relative_path

    return os.path.normpath(os.path.join(root_path, relative_path))


def generate_uniq_timestamp_request_id() -> str:
    timestamp_ms_int = int(datetime.datetime.now().timestamp() * 100_000)
    random_hex_part = f'{random.randrange(16**17):017x}'
    return f'{timestamp_ms_int}{random_hex_part}'


def check_request_id(request_id: str) -> bool:
    try:
        int(request_id, 16)
        return True
    except ValueError:
        logger.error(f'request_id = {request_id} is not valid hex-format')
        return False


async def gather_list(*coros):
    """
    Similar to asyncio.gather, but None can be used in coros_or_futures param
    """
    return await asyncio.gather(*[asyncio.sleep(0) if coro is None else coro for coro in coros])


async def gather_dict(coro_dict):
    """
    None can be used in coros, see :func:`gather_list`
    """
    results = await gather_list(*coro_dict.values())
    return dict(zip(coro_dict.keys(), results))

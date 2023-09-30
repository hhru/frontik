from __future__ import annotations

import asyncio
import datetime
import logging
import os.path
import random
import re
from string import Template
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from uuid import uuid4

from http_client.util import any_to_bytes, any_to_unicode, to_unicode
from tornado.escape import utf8

if TYPE_CHECKING:
    from typing import Any

    from frontik.handler import PageHandler

logger = logging.getLogger('util')


def safe_template(format_string: str, **kwargs: Any) -> str:
    """Safe templating using PEP-292 template strings
    (see https://docs.python.org/3/library/string.html#template-strings).

    :param str format_string: a string to be formatted.
    :param kwargs: placeholder values.
    :return str: formatted string.
    """
    return Template(to_unicode(format_string)).safe_substitute(**kwargs)


def make_qs(query_args: dict) -> str:
    return urlencode([(k, v) for k, v in query_args.items() if v is not None], doseq=True)


def make_body(data):
    return make_qs(data) if isinstance(data, dict) else any_to_bytes(data)


def make_url(base: str, **query_args: Any) -> str:
    """
    Builds URL from base part and query arguments passed as kwargs.
    Returns unicode string
    """
    qs = make_qs(query_args)

    if qs:
        return to_unicode(base) + ('&' if '?' in base else '?') + qs
    else:
        return to_unicode(base)


def decode_string_from_charset(value: bytes, charsets: tuple = ('cp1251',)) -> str:
    if isinstance(value, str):
        return value

    decoded_body = None
    for c in charsets:
        try:
            decoded_body = value.decode(c)
            break
        except UnicodeError:
            continue

    if decoded_body is None:
        msg = 'Could not decode string (tried: {})'.format(', '.join(charsets))
        raise UnicodeError(msg)

    return decoded_body


def choose_boundary():
    """
    Our embarassingly-simple replacement for mimetools.choose_boundary.
    See https://github.com/kennethreitz/requests/blob/master/requests/packages/urllib3/filepost.py
    """
    return utf8(uuid4().hex)


def get_cookie_or_url_param_value(handler: PageHandler, param_name: str) -> str | None:
    return handler.get_argument(param_name, handler.get_cookie(param_name, None))


def reverse_regex_named_groups(pattern: str, *args: Any, **kwargs: Any) -> str:
    class GroupReplacer:
        def __init__(self, args: Any, kwargs: Any) -> None:
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
                    msg = 'Cannot reverse regex: required number of arguments not found'
                    raise ValueError(msg)

            return any_to_unicode(value)

    result = re.sub(r'\(([^)]+)\)', GroupReplacer(args, kwargs), to_unicode(pattern))
    return result.replace('^', '').replace('$', '')


def get_abs_path(root_path: str, relative_path: str | None) -> str:
    if relative_path is None or os.path.isabs(relative_path):
        return relative_path  # type: ignore

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
        logger.error('request_id = %s is not valid hex-format', request_id)
        return False


async def gather_list(*coros: Any) -> tuple:
    """
    Similar to asyncio.gather, but None can be used in coros_or_futures param
    """
    return await asyncio.gather(*[asyncio.sleep(0) if coro is None else coro for coro in coros])


async def gather_dict(coro_dict: dict) -> dict:
    """
    None can be used in coros, see :func:`gather_list`
    """
    results = await gather_list(*coro_dict.values())
    return dict(zip(coro_dict.keys(), results, strict=True))

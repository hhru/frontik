import asyncio
import datetime
import logging
import os.path
import random
import re
import socket
import sys
from asyncio import Task
from collections.abc import Coroutine, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from string import Template
from typing import Any, Optional
from urllib.parse import urlencode
from uuid import uuid4

from http_client.util import any_to_bytes, any_to_unicode, to_unicode
from tornado.escape import utf8
from tornado.web import httputil

logger = logging.getLogger('util')
_async_tasks = set()


class Sentinel:
    pass


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


def decode_string_from_charset(value: bytes, charsets: tuple[str, ...] = ('cp1251',)) -> str:
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


def get_cookie_or_param_from_request(tornado_request: httputil.HTTPServerRequest, param_name: str) -> Optional[str]:
    query = tornado_request.query_arguments.get(param_name)
    if query:
        return query[-1].decode()

    cookie = tornado_request.cookies.get(param_name, None)
    if cookie:
        return cookie.value

    return None


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


def get_abs_path(root_path: str, relative_path: Optional[str]) -> str:
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


async def gather_list(*coros: Any) -> list:
    """
    Similar to asyncio.gather, but None can be used in coros_or_futures param
    """
    return await asyncio.gather(*[asyncio.sleep(0) if coro is None else coro for coro in coros])


async def gather_dict(coro_dict: dict) -> dict:
    """
    None can be used in coros, see :func:`gather_list`
    """
    results = await gather_list(*coro_dict.values())
    return dict(zip(coro_dict.keys(), results))


def bind_socket(host: str, port: int) -> socket.socket:
    sock = socket.socket(family=socket.AF_INET)
    sock.setblocking(False)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    try:
        sock.bind((host, port))
    except OSError as exc:
        logger.error(exc)
        sys.exit(1)

    sock.set_inheritable(True)
    sock.listen()
    return sock


def run_async_task(coro: Coroutine) -> Task:
    async def _wrapped(_coro: Coroutine) -> None:
        try:
            await _coro
        except Exception:
            logger.exception('frontik async task was failed')

    task = asyncio.create_task(_wrapped(coro))
    _async_tasks.add(task)
    task.add_done_callback(_async_tasks.discard)
    return task


@contextmanager
def set_contextvar(contextvar: ContextVar, value: Any) -> Iterator:
    token = contextvar.set(value)
    try:
        yield
    finally:
        contextvar.reset(token)

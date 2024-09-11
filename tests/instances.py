from __future__ import annotations

import base64
import json
import random
import socket
import subprocess
import sys
import time
from itertools import chain
from typing import TYPE_CHECKING, Optional

import requests
from lxml import etree
from tornado.escape import to_unicode, utf8

from frontik import options
from tests import FRONTIK_ROOT

if TYPE_CHECKING:
    from builtins import function
    from collections.abc import Callable
    from typing import Any

    from requests.models import Response


FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'
TEST_PROJECTS = f'{FRONTIK_ROOT}/tests/projects'


def _run_command(command: str, port: int) -> subprocess.Popen:
    python = sys.executable
    executable = f'{python} {command} --port={port}'
    return subprocess.Popen(executable.split())


def find_free_port(from_port: int = 9000, to_port: int = 10000) -> int:
    random_start = random.randint(from_port, to_port)

    for port in chain(range(random_start, to_port), range(from_port, random_start)):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('', port))
            break
        except Exception:
            pass
        finally:
            s.close()
    else:
        msg = f'No empty port in range {from_port}..{to_port} for frontik test instance'
        raise AssertionError(msg)

    return port


def create_basic_auth_header(credentials: str) -> str:
    return f'Basic {to_unicode(base64.b64encode(utf8(credentials)))}'


class FrontikTestInstance:
    def __init__(self, command: str, *, allow_to_create_log_files: bool = False) -> None:
        if not allow_to_create_log_files and options.LOG_DIR_OPTION_NAME in command:
            raise Exception('Log to file is prohibited it tests by default. use allow_to_create_log_files if needed')
        self.command = command
        self.popen: subprocess.Popen
        self.port: Optional[int] = None

    def start(self) -> None:
        if self.port:
            return
        self.port = find_free_port()
        self.popen = _run_command(self.command, self.port)

        for _i in range(50):
            try:
                time.sleep(0.1)
                response = self.get_page('status')
                if response.status_code == 200:
                    return
            except Exception:
                pass

        raise AssertionError('Failed to start Frontik instance')

    def start_with_check(self, check_function: Callable) -> None:
        self.port = find_free_port()
        self.popen = _run_command(self.command, self.port)
        check_function(self)

    def stop(self) -> None:
        if not self.port:
            return

        self.popen.terminate()
        self.popen.wait(300)
        self.port = None

    def is_alive(self) -> bool:
        return self.popen.poll() is None

    def get_page(
        self,
        page: str,
        notpl: bool = False,
        method: Callable | function = requests.get,
        **kwargs: Any,
    ) -> Response:
        if not self.port:
            self.start()

        url = 'http://127.0.0.1:{port}/{page}{notpl}'.format(
            port=self.port,
            page=page.format(port=self.port),
            notpl=('?' if '?' not in page else '&') + 'notpl' if notpl else '',
        )

        # workaround for different versions of requests library
        if 'auth' in kwargs and requests.__version__ > '1.0':
            from requests.auth import HTTPBasicAuth

            auth = kwargs['auth']
            kwargs['auth'] = HTTPBasicAuth(auth[1], auth[2])

        kwargs['timeout'] = 4

        return method(url, **kwargs)  # type: ignore

    def get_page_xml(
        self,
        page: str,
        notpl: bool = False,
        method: Callable = requests.get,
        **kwargs: Any,
    ) -> etree.Element:
        content = utf8(self.get_page(page, notpl=notpl, method=method, **kwargs).content)

        try:
            return etree.fromstring(content)
        except Exception as e:
            msg = f'failed to parse xml ({e}): "{content!s}"'
            raise Exception(msg)

    def get_page_json(self, page: str, notpl: bool = False, method: Callable = requests.get, **kwargs: Any) -> Any:
        content = self.get_page_text(page, notpl=notpl, method=method, **kwargs)

        try:
            return json.loads(content)
        except Exception as e:
            msg = f'failed to parse json ({e}): "{content}"'
            raise Exception(msg)

    def get_page_text(self, page: str, notpl: bool = False, method: Callable = requests.get, **kwargs: Any) -> str:
        return to_unicode(self.get_page(page, notpl=notpl, method=method, **kwargs).content)


common_frontik_start_options = f'--{options.STDERR_LOG_OPTION_NAME}=True'

frontik_consul_mock_app = FrontikTestInstance(
    f'{FRONTIK_RUN} --app_class=tests.projects.consul_mock_app.TestApplication '
    f' --config={TEST_PROJECTS}/frontik_consul_mock.cfg {common_frontik_start_options}',
)

frontik_test_app = FrontikTestInstance(
    f'{FRONTIK_RUN} --app_class=tests.projects.test_app.TestApplication '
    f' --config={TEST_PROJECTS}/frontik_debug.cfg {common_frontik_start_options} '
)
frontik_re_app = FrontikTestInstance(
    f'{FRONTIK_RUN} --app_class=tests.projects.re_app.TestApplication '
    f' --config={TEST_PROJECTS}/frontik_debug.cfg {common_frontik_start_options} '
)

frontik_no_debug_app = FrontikTestInstance(
    f'{FRONTIK_RUN} --app_class=tests.projects.no_debug_app.TestApplication '
    f' --config={TEST_PROJECTS}/frontik_no_debug.cfg {common_frontik_start_options} '
)

frontik_broken_config_app = FrontikTestInstance(
    f'{FRONTIK_RUN} --app_class=tests.projects.broken_config_app.TestApplication '
    f' --config={TEST_PROJECTS}/frontik_debug.cfg {common_frontik_start_options} '
)

frontik_broken_init_async_app = FrontikTestInstance(
    f'{FRONTIK_RUN} --app_class=tests.projects.broken_async_init_app.TestApplication '
    f' --config={TEST_PROJECTS}/frontik_debug.cfg {common_frontik_start_options} '
)

frontik_balancer_app = FrontikTestInstance(
    f'{FRONTIK_RUN} --app_class=tests.projects.balancer_app.TestApplication '
    f' --config={TEST_PROJECTS}/frontik_no_debug.cfg {common_frontik_start_options} '
)

frontik_broken_balancer_app = FrontikTestInstance(
    f'{FRONTIK_RUN} --app_class=tests.projects.broken_balancer_app.TestApplication '
    f' --config={TEST_PROJECTS}/frontik_debug.cfg {common_frontik_start_options} '
)

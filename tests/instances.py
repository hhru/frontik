import base64
import json
import socket
import subprocess
import sys
import time
from distutils.spawn import find_executable

import requests
from lxml import etree
from tornado.escape import to_unicode, utf8

try:
    import coverage
    USE_COVERAGE = '--with-coverage' in sys.argv
except ImportError:
    USE_COVERAGE = False


def run_command(command, port):
    if USE_COVERAGE:
        template = '{exe} {coverage} run {command} {args}'
    else:
        template = '{exe} {command} {args}'

    executable = template.format(
        exe=sys.executable,
        coverage=find_executable('coverage'),
        command=command,
        args=f'--port={port}',
    )

    return subprocess.Popen(executable.split())


def find_free_port(from_port=9000, to_port=10000):
    for port in range(from_port, to_port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('', port))
            break
        except Exception:
            pass
        finally:
            s.close()
    else:
        raise AssertionError(f'No empty port in range {from_port}..{to_port} for frontik test instance')

    return port


def create_basic_auth_header(credentials):
    return 'Basic {}'.format(to_unicode(base64.b64encode(utf8(credentials))))


class FrontikTestInstance:
    def __init__(self, command: str):
        self.command = command
        self.popen = None
        self.port = None

    def start(self):
        self.port = find_free_port()
        self.popen = run_command(self.command, self.port)

        for i in range(10):
            try:
                time.sleep(0.2)
                response = self.get_page('status')
                if response.status_code == 200:
                    return
            except Exception:
                pass

        assert False, 'Failed to start Frontik instance'

    def stop(self):
        if not self.port:
            return

        self.popen.terminate()
        self.port = None

    def get_page(self, page, notpl=False, method=requests.get, **kwargs):
        if not self.port:
            self.start()

        url = 'http://127.0.0.1:{port}/{page}{notpl}'.format(
            port=self.port,
            page=page.format(port=self.port),
            notpl=('?' if '?' not in page else '&') + 'notpl' if notpl else ''
        )

        # workaround for different versions of requests library
        if 'auth' in kwargs and requests.__version__ > '1.0':
            from requests.auth import HTTPBasicAuth
            auth = kwargs['auth']
            kwargs['auth'] = HTTPBasicAuth(auth[1], auth[2])

        kwargs['timeout'] = 1

        return method(url, **kwargs)

    def get_page_xml(self, page, notpl=False, method=requests.get):
        content = utf8(self.get_page(page, notpl=notpl, method=method).content)

        try:
            return etree.fromstring(content)
        except Exception as e:
            raise Exception(f'failed to parse xml ({e}): "{content}"')

    def get_page_json(self, page, notpl=False, method=requests.get):
        content = self.get_page_text(page, notpl=notpl, method=method)

        try:
            return json.loads(content)
        except Exception as e:
            raise Exception(f'failed to parse json ({e}): "{content}"')

    def get_page_text(self, page, notpl=False, method=requests.get):
        return to_unicode(self.get_page(page, notpl=notpl, method=method).content)


frontik_test_app = FrontikTestInstance(
    './frontik-test --app=tests.projects.test_app --config=tests/projects/frontik_debug.cfg --log_dir=.'
)

frontik_re_app = FrontikTestInstance(
    './frontik-test --app=tests.projects.re_app --config=tests/projects/frontik_debug.cfg --log_dir=.'
)

frontik_no_debug_app = FrontikTestInstance(
    './frontik-test --app=tests.projects.no_debug_app --config=tests/projects/frontik_no_debug.cfg --log_dir=.'
)

frontik_broken_config_app = FrontikTestInstance(
    './frontik-test --app=tests.projects.broken_config_app --config=tests/projects/frontik_debug.cfg --log_dir=.'
)

frontik_broken_init_async_app = FrontikTestInstance(
    './frontik-test --app=tests.projects.broken_async_init_app --config=tests/projects/frontik_debug.cfg --log_dir=.'
)

frontik_balancer_app = FrontikTestInstance(
    './frontik-test --app=tests.projects.balancer_app --config=tests/projects/frontik_debug.cfg --log_dir=.'
)

frontik_broken_balancer_app = FrontikTestInstance(
    './frontik-test --app=tests.projects.broken_balancer_app --config=tests/projects/frontik_debug.cfg --log_dir=.'
)

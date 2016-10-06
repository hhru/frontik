# coding=utf-8

import base64
from distutils.spawn import find_executable
import json
import os
import socket
import subprocess
import sys
import time

from lxml import etree
from tornado.escape import to_unicode, utf8
import requests

from . import FRONTIK_ROOT
from frontik.server import supervisor

try:
    import coverage
    USE_COVERAGE = '--with-coverage' in sys.argv
except ImportError:
    USE_COVERAGE = False


def run_supervisor_command(supervisor_script, port, command):
    if USE_COVERAGE:
        template = '{exe} {coverage} run {supervisor} --with-coverage {args} {command}'
    else:
        template = '{exe} {supervisor} {args} {command}'

    args = '--start_port={port} --workers_count=1 --pidfile_template={pidfile} --logfile_template={logfile}'.format(
        port=port,
        pidfile=os.path.join(FRONTIK_ROOT, '{}.%(port)s.pid'.format(supervisor_script)),
        logfile=os.path.join(FRONTIK_ROOT, 'frontik_test.log')
    )

    executable = template.format(
        exe=sys.executable,
        coverage=find_executable('coverage'),
        supervisor=supervisor_script,
        args=args,
        command=command
    )

    return subprocess.Popen(executable.split(), stderr=subprocess.PIPE)


def find_free_port(from_port=9000, to_port=10000):
    for port in range(from_port, to_port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('', port))
            s.close()
            break
        except:
            pass
    else:
        raise AssertionError('No empty port in range {}..{} for frontik test instance'.format(from_port, to_port))

    return port


def create_basic_auth_header(credentials):
    return 'Basic {}'.format(to_unicode(base64.b64encode(utf8(credentials))))


class FrontikTestInstance(object):
    def __init__(self, supervisor_script):
        self.supervisor_script = supervisor_script
        self.port = None

    def start(self):
        self.port = find_free_port()
        run_supervisor_command(self.supervisor_script, self.port, 'start')
        self.wait_for(lambda: supervisor.worker_is_running(self.port), 50)

        assert self.get_page('status').status_code == 200

    def stop(self):
        if not self.port:
            return

        process = run_supervisor_command(self.supervisor_script, self.port, 'stop')
        assert process.wait() == 0
        self.port = None

    @staticmethod
    def wait_for(fun, steps):
        for i in range(steps):
            if fun():
                return
            time.sleep(0.1)  # up to 5 seconds with steps=50

        assert fun()

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

        return method(url, **kwargs)

    def get_page_xml(self, page, notpl=False):
        content = utf8(self.get_page(page, notpl).content)

        try:
            return etree.fromstring(content)
        except Exception as e:
            raise Exception('failed to parse xml ({}): "{}"'.format(e, content))

    def get_page_json(self, page, notpl=False):
        content = self.get_page_text(page, notpl)

        try:
            return json.loads(content)
        except Exception as e:
            raise Exception('failed to parse json ({}): "{}"'.format(e, content))

    def get_page_text(self, page, notpl=False):
        return to_unicode(self.get_page(page, notpl).content)


frontik_broken_app = FrontikTestInstance('supervisor-brokenapp')
frontik_test_app = FrontikTestInstance('supervisor-testapp')
frontik_re_app = FrontikTestInstance('supervisor-reapp')
frontik_no_debug_app = FrontikTestInstance('supervisor-nodebug')

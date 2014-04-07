# coding=utf-8

import contextlib
import socket
import time
import urllib2

from lxml import etree

import tornado.options
import tornado_util.supervisor as supervisor


class FrontikTestInstance(object):
    def __init__(self, cfg='./tests/projects/frontik.cfg'):
        tornado.options.parse_config_file(cfg)
        self.cfg = cfg
        self.port = None
        self.supervisor = supervisor

    def start(self):
        for port in xrange(9000, 10000):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(('', port))
                s.close()
                break
            except:
                pass
        else:
            raise AssertionError('No empty port in range 9000..10000 for frontik test instance')

        supervisor.start_worker('./dev_run.py', self.cfg, port)
        self.wait_for(lambda: supervisor.is_running(port))
        self.port = port

    def __del__(self):
        self.supervisor.stop_worker(self.port)
        self.wait_for(lambda: not(self.supervisor.is_running(self.port)))
        self.supervisor.rm_pidfile(self.port)

    def wait_for(self, fun, n=50):
        for i in range(n):
            if fun():
                return
            time.sleep(0.1)
        assert(fun())

    @contextlib.contextmanager
    def instance(self):
        if not self.port:
            self.start()
        yield self.port

    @contextlib.contextmanager
    def get_page(self, page, notpl=False):
        with self.instance() as srv_port:
            url = 'http://localhost:{0}/{1}{2}{3}'.format(
                srv_port, page, '/?' if '?' not in page else '&', 'notpl' if notpl else '')
            yield urllib2.urlopen(url)

    @contextlib.contextmanager
    def get_page_xml(self, page, notpl=False):
        with self.get_page_text(page, notpl) as data:
            try:
                res = etree.fromstring(data)
            except:
                print 'failed to parse xml: "{0}"'.format(data)
                raise

            yield res

    @contextlib.contextmanager
    def get_page_text(self, page, notpl=False):
        with self.get_page(page, notpl) as response:
            yield response.read()

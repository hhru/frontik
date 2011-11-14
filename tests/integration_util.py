# -*- coding: utf-8 -*-

import time
import urllib2
import contextlib
import httplib
import socket
import subprocess
import lxml.etree as etree

import tornado_util.supervisor as supervisor
import tornado.options
import frontik.options

def get_page(port, page, xsl=False):
    url = "http://localhost:{0}/{1}{2}".format(port, page,
                                               ("/?" if "?" not in page else "&") + ("noxsl=true" if not xsl else ""))
    data = urllib2.urlopen(url)
    print url
    return data


class FrontikTestInstance(object):
    def __init__(self, cfg="./tests/projects/frontik.cfg"):
        self.cfg = cfg
        tornado.options.parse_config_file(self.cfg)
        self.port = None
        self.supervisor = supervisor

    def start(self):
        for port in xrange(9000, 10000):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("", port))
                s.close()
                break
            except:
                pass
        else:
            raise AssertionError("no empty port in 9000-10000 for frontik test instance")

        supervisor.start_worker("./dev_run.py", self.cfg, port)
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
        try:
            yield self.port
        finally:
            data = urllib2.urlopen("http://localhost:{0}/ph_count/".format(self.port)).read().split("\n")
            ph_count = int(data[0])
            refs = data[1:]
            print "ph_count={0}".format(ph_count)
            print "refs={0}".format(refs)


    @contextlib.contextmanager
    def get_page_xml(self, page_name, xsl=True):
        with self.instance() as srv_port:
            data = get_page(srv_port, page_name, xsl).read()
    
            try:
                res = etree.fromstring(data)
            except:
                print "failed to parse xml: \"%s\"" % (data,)
                raise
    
            yield res

    @contextlib.contextmanager
    def get_page_text(self, page_name, xsl=True):
        with self.instance() as srv_port:
            data = get_page(srv_port, page_name, xsl).read()
            yield data



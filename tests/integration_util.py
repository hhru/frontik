# -*- coding: utf-8 -*-

import time
import urllib2
import contextlib
import httplib
import socket
import subprocess
import lxml.etree as etree

import tornado_util.supervisor as supervisor

def get_page(port, page, xsl=False):
    data = urllib2.urlopen("http://localhost:%s/%s/%s" % (port, page, "?noxsl=true" if not xsl else "" ))
    
    return data


def wait_for(fun, n=10):
    for i in range(n):
        if fun():
            return
        time.sleep(0.5)

    assert(fun())


class FrontikTestInstance(object):
    def __init__(self, cfg="./tests/projects/frontik.cfg"):
        self.cfg = cfg
    
    @contextlib.contextmanager
    def instance(self):
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

        subprocess.Popen(["python",
                          "./frontik_srv.py",
                          "--config=%s" % (self.cfg,),
                          "--port=%s" % (port,)])
        wait_for(lambda: supervisor.is_running(port))
        try:
            yield port
        finally:
            data = urllib2.urlopen("http://localhost:{0}/ph_count/".format(port)).read().split("\n")
            ph_count = int(data[0])
            refs = data[1:]
            print "ph_count={0}".format(ph_count)
            print "refs={0}".format(refs)

            supervisor.stop_worker(port)
            wait_for(lambda: not(supervisor.is_running(port)))
            

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



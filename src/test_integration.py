# -*- coding: utf-8 -*-

from __future__ import with_statement

import subprocess
import nose
import urllib2
import httplib
import time
from functools import partial
import lxml.etree as etree

# XXX взять эти функции из frontik.supervisor, когда он появится
def is_running(port):
    try:
        urllib2.urlopen('http://localhost:%s/status/' % (port,))
        return True
    except urllib2.URLError:
        return False
    except urllib2.HTTPError:
        return False

def stop_worker(port):
    try:
        urllib2.urlopen('http://localhost:%s/stop/' % (port,))
    except urllib2.URLError:
        pass
    except httplib.BadStatusLine:
        pass

def get_page(port, page):
    return etree.fromstring(urllib2.urlopen('http://localhost:%s/page/%s/' % (port, page)).read())

def wait_for(fun, n=10):
    for i in range(n):
        if fun():
            return
        time.sleep(0.1)

    assert(fun())

class FrontikTestInstance:
    def __enter__(self):
        for port in xrange(9000, 10000):
            if not is_running(port):
                self.port = port
                break
        else:
            raise AssertionError('no empty port in 9000-10000 for frontik test instance')

        subprocess.Popen(['python',
                          '../src/frontik_srv.py',
                          '--logfile=./frontik_test.log',
                          '--loglevel=debug',
                          '--host=localhost',
                          '--daemonize=False',
                          '--document_root=./test/',
                          '--port=%s' % (self.port,)])
        wait_for(lambda: is_running(self.port))

        return self.port

    def __exit__(self, exc_type, exc_value, traceback):
        stop_worker(self.port)
        wait_for(lambda: not(is_running(self.port)))

def simple_test():
    with FrontikTestInstance() as srv_port:
        xml = get_page(srv_port, 'simple')
        assert(not xml.find('ok') is None)

def compose_doc_test():
    with FrontikTestInstance() as srv_port:
        xml = get_page(srv_port, 'compose_doc')

        assert(not xml.find('a') is None)
        assert(xml.findtext('a') == 'aaa')

        assert(not xml.find('b') is None)
        assert(xml.findtext('b') == 'bbb')

        assert(not xml.find('c') is None)
        assert(xml.findtext('c') is None)

if __name__ == '__main__':
    nose.main()

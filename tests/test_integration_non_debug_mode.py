# -*- coding: utf-8 -*-

from __future__ import with_statement

import socket
import subprocess
import nose
import urllib2
import httplib
import time
from functools import partial
import lxml.etree as etree
import contextlib

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

def get_page(port, page, xsl=False):
    data = urllib2.urlopen('http://localhost:%s/%s/%s' % (port, page, "?noxsl=true" if not xsl else "" ))
    
    return data

def wait_for(fun, n=10):
    for i in range(n):
        if fun():
            return
        time.sleep(0.5)

    assert(fun())


class FrontikTestInstance(object):
    def __enter__(self):
        for port in xrange(9000, 10000):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(('', port))
                s.close()
                self.port = port
                break
            except:
                pass
        else:
            raise AssertionError('no empty port in 9000-10000 for frontik test instance')
        
        subprocess.Popen(["./run_frontik.sh",
                          "--config=./tests/projects/frontik_non_debug_mode.cfg",
                          "--",
                          "--port=%s" % (self.port,)])
        wait_for(lambda: is_running(self.port))

        return self.port

    def __exit__(self, exc_type, exc_value, traceback):
        stop_worker(self.port)
        wait_for(lambda: not(is_running(self.port)))


@contextlib.contextmanager
def frontik_server():
    with FrontikTestInstance() as srv_port:
        yield srv_port

        data = urllib2.urlopen('http://localhost:{0}/ph_count/'.format(srv_port)).read().split('\n')
        ph_count = int(data[0])
        refs = data[1:]
        print 'ph_count={0}'.format(ph_count)
        print 'refs={0}'.format(refs)

        #if ph_count > 0:
            #urllib2.urlopen('http://localhost:{0}/pdb/'.format(srv_port))
            #assert(ph_count == 0)
        

@contextlib.contextmanager
def frontik_get_page_xml(page_name, xsl=True):
    with frontik_server() as srv_port:
        data = get_page(srv_port, page_name, xsl).read()

        try:
            res = etree.fromstring(data)
        except:
            print 'failed to parse xml: "%s"' % (data,)
            raise

        yield res

@contextlib.contextmanager
def frontik_get_page_text(page_name, xsl=True):
    with frontik_server() as srv_port:
        data = get_page(srv_port, page_name, xsl).read()
        yield data


def simple2_test():
    with frontik_get_page_text('test_app/simple') as html:
        assert(not html.find('ok') is None)

def test_basic_auth_fail():
    with frontik_server() as srv_port:
        try:
            res = urllib2.urlopen('http://localhost:{0}/test_app/basic_auth/'.format(srv_port)).info()
            assert(res.getcode() != 200)
        except urllib2.HTTPError, e:
            assert(e.code == 401)


def test_basic_auth_fail_on_wrong_pass():
    with frontik_server() as srv_port:
        page_url = 'http://localhost:{0}/test_app/basic_auth/'.format(srv_port)
        
        import urllib2
        # Create an OpenerDirector with support for Basic HTTP Authentication...
        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password(realm='Secure Area',
                                  uri=page_url,
                                  user='user',
                                  passwd='bad')
        opener = urllib2.build_opener(auth_handler)
        try: 
            res = opener.open(page_url)
            assert(res.getcode() != 200)
        except urllib2.HTTPError, e:
            assert(e.code == 401)

def test_basic_auth_pass():
    with frontik_server() as srv_port:
        page_url = 'http://localhost:{0}/test_app/basic_auth/'.format(srv_port)
        
        import urllib2
        # Create an OpenerDirector with support for Basic HTTP Authentication...
        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password(realm='Secure Area',
                                  uri=page_url,
                                  user='user',
                                  passwd='god')
        opener = urllib2.build_opener(auth_handler)
        res = opener.open(page_url)

        assert(res.getcode() == 200)
    

if __name__ == '__main__':
    nose.main()

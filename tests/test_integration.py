# -*- coding: utf-8 -*-
from __future__ import with_statement

import contextlib
import httplib
import socket
import subprocess
import time
import urllib2

import lxml.etree as etree
import nose


# XXX взять эти функции из frontik.supervisor, когда он появится
def is_running(port):
    try:
        urllib2.urlopen("http://localhost:%s/status/" % (port,))
        return True
    except urllib2.URLError:
        return False
    except urllib2.HTTPError:
        return False

def stop_worker(port):
    try:
        urllib2.urlopen("http://localhost:%s/stop/" % (port,))
    except urllib2.URLError:
        pass
    except httplib.BadStatusLine:
        pass

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
    def __enter__(self):
        for port in xrange(9000, 10000):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("", port))
                s.close()
                self.port = port
                break
            except:
                pass
        else:
            raise AssertionError("no empty port in 9000-10000 for frontik test instance")

        subprocess.Popen(["./run_frontik.sh",
                          "--config=./tests/projects/frontik.cfg",
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

        data = urllib2.urlopen("http://localhost:{0}/ph_count/".format(srv_port)).read().split("\n")
        ph_count = int(data[0])
        refs = data[1:]
        print "ph_count={0}".format(ph_count)
        print "refs={0}".format(refs)

        #if ph_count > 0:
            #urllib2.urlopen("http://localhost:{0}/pdb/".format(srv_port))
            #assert(ph_count == 0)
        

@contextlib.contextmanager
def frontik_get_page_xml(page_name, xsl=True):
    with frontik_server() as srv_port:
        data = get_page(srv_port, page_name, xsl).read()

        try:
            res = etree.fromstring(data)
        except:
            print "failed to parse xml: \"%s\"" % (data,)
            raise

        yield res

@contextlib.contextmanager
def frontik_get_page_text(page_name, xsl=True):
    with frontik_server() as srv_port:
        data = get_page(srv_port, page_name, xsl).read()
        yield data


def simple_test():
    with frontik_get_page_text("test_app/simple") as html:
        assert(not html.find("ok") is None)


def test_inexistent_page():
    with FrontikTestInstance() as srv_port:
        try:
            get_page(srv_port, "inexistent_page")
        except urllib2.HTTPError, e:
            assert(e.code == 404)


def compose_doc_test():
    with frontik_get_page_xml("test_app/compose_doc") as xml:
        assert(not xml.find("a") is None)
        assert(xml.findtext("a") == "aaa")

        assert(not xml.find("b") is None)
        assert(xml.findtext("b") == "bbb")

        assert(not xml.find("c") is None)
        assert(xml.findtext("c") in [None, ""])


def xsl_transformation_test():
    with frontik_get_page_xml("test_app/simple") as html:
        assert (etree.tostring(html) == "<html><body><h1>ok</h1></body></html>")


def test_content_type_with_xsl():
    with FrontikTestInstance() as srv_port:
        assert(get_page(srv_port, "test_app/simple", xsl=True).headers["content-type"].startswith("text/html"))


def test_xsl_fail():
    with FrontikTestInstance() as srv_port:
        try:
            get_page(srv_port, "test_app/xsl_fail", xsl=True)
            raise Exception("get_page should`ve failed with HTTPError 500")
        except urllib2.HTTPError, e:
            assert(e.code == 500)


def test_content_type_wo_xsl():
    with FrontikTestInstance() as srv_port:
        assert(get_page(srv_port, "test_app/simple", xsl=False).headers["content-type"].startswith("application/xml"))


def xml_include_test():
    with frontik_get_page_xml("test_app/include_xml") as xml:
        assert(xml.findtext("a") == "aaa")


def test_root_node_frontik_attribute():
    with frontik_get_page_xml("test_app/simple_xml") as xml:
        assert(xml.get("frontik") == "true")
        assert(xml.find("doc").get("frontik", None) is None)


def test_fib0():
    with frontik_server() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/fib/?port={0}&n=0".format(srv_port)).read())
        # 0 1 2 3 4 5 6
        # 1 1 2 3 5 8 13
        assert(int(xml.text) == 1)


def test_fib2():
    with frontik_server() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/fib/?port={0}&n=2".format(srv_port)).read())
        # 0 1 2 3 4 5 6
        # 1 1 2 3 5 8 13
        assert(int(xml.text) == 2)


def test_fib6():
    with frontik_server() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/fib/?port={0}&n=6".format(srv_port)).read())
        # 0 1 2 3 4 5 6
        # 1 1 2 3 5 8 13
        assert(int(xml.text) == 13)


def test_timeout():
    with frontik_server() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/long_page_request/?port={0}".format(srv_port)).read())

        assert(xml.text == "error")

        time.sleep(2)


def test_basic_auth_fail():
    with frontik_server() as srv_port:
        try:
            urllib2.urlopen("http://localhost:{0}/test_app/basic_auth/".format(srv_port)).info()
        except urllib2.HTTPError, e:
            assert(e.code == 401)


def test_basic_auth_pass():
    with frontik_server() as srv_port:
        page_url = "http://localhost:{0}/test_app/basic_auth/".format(srv_port)
        
        import urllib2
        # Create an OpenerDirector with support for Basic HTTP Authentication...
        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password(realm="Secure Area",
                                  uri=page_url,
                                  user="user",
                                  passwd="god")
        opener = urllib2.build_opener(auth_handler)
        res = opener.open(page_url)

        assert(res.getcode() == 200)
    

def test_multi_app_simple():
    with frontik_get_page_xml("test_app/use_lib") as xml:
        assert xml.text == "10"

if __name__ == "__main__":
    nose.main()

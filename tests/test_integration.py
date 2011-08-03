# -*- coding: utf-8 -*-
from __future__ import with_statement

import time
import urllib2
import lxml.etree as etree
import nose
import frontik.handler

from integration_util import get_page, FrontikTestInstance

frontik_debug = FrontikTestInstance("./tests/projects/frontik.cfg")


def simple_test():
    with frontik_debug.get_page_text("test_app/simple") as html:
        assert(not html.find("ok") is None)


def not_simple_test():
    with frontik_debug.get_page_text("re_app/not_simple") as html:
        assert(not html.find("ok") is None)

def simple_map2fs_test():
    with frontik_debug.get_page_text("re_app/simple") as html:
        assert(not html.find("ok") is None)

def cdata_test():
    with frontik_debug.instance() as srv_port:
        with frontik_debug.get_page_text("test_app/cdata/?port=%s" % srv_port) as html:
            print html
            assert(not html.find("test") is None)
            assert(not html.find("CDATA") is None)

def url_types_test_1():
    with frontik_debug.instance() as srv_port:
        assert(not urllib2.urlopen("http://localhost:%s//re_app/not_simple" % srv_port).read().find("ok") is None)
        assert(not urllib2.urlopen("http://localhost:%s//re_app/simple" % srv_port).read().find("ok") is None)
def url_types_test_2():
    with frontik_debug.instance() as srv_port:
        assert(not urllib2.urlopen("http://localhost:%s/re_app//not_simple" % srv_port).read().find("ok") is None)
        assert(not urllib2.urlopen("http://localhost:%s/re_app//simple" % srv_port).read().find("ok") is None)

def id_rewrite_test():
    value = "some"
    with frontik_debug.get_page_text("re_app/id/%s" % value) as html:
        assert(not html.find(value) is None)

def ids_rewrite_test():
    values = ["some", "another"]
    with frontik_debug.get_page_text("re_app/id/%s" % ",".join(values)) as html:
        assert(all(map(html.find, values)))

def test_inexistent_page():
    with frontik_debug.instance() as srv_port:
        try:
            with get_page(srv_port, "inexistent_page") as html:
                assert False
        except urllib2.HTTPError, e:
            assert(e.code == 404)


def compose_doc_test():
    with frontik_debug.get_page_xml("test_app/compose_doc") as xml:
        assert(not xml.find("a") is None)
        assert(xml.findtext("a") == "aaa")

        assert(not xml.find("b") is None)
        assert(xml.findtext("b") == "bbb")

        assert(not xml.find("c") is None)
        assert(xml.findtext("c") in [None, ""])


def xsl_transformation_test():
    with frontik_debug.get_page_xml("test_app/simple") as html:
        assert (etree.tostring(html) == "<html><body><h1>ok</h1></body></html>")


def test_content_type_with_xsl():
    with frontik_debug.instance() as srv_port:
        assert(get_page(srv_port, "test_app/simple", xsl=True).headers["content-type"].startswith("text/html"))


def test_xsl_fail():
    # this test became bizarre because of Firefox browser, see handler_xml_debug.py
    with frontik_debug.instance() as srv_port:
        try:
            _ = urllib2.urlopen('http://localhost:{0}/test_app/xsl_fail'.format(srv_port)).info()
            raise Exception("get_page should`ve failed with HTTPError 500")
        except urllib2.HTTPError, e:
            assert(any(map(lambda x: 'XSLTApplyError' in x, e.readlines())))
            assert(e.code == 500)


def test_content_type_wo_xsl():
    with frontik_debug.instance() as srv_port:
        assert(get_page(srv_port, "test_app/simple", xsl=False).headers["content-type"].startswith("application/xml"))


def xml_include_test():
    with frontik_debug.get_page_xml("test_app/include_xml") as xml:
        assert(xml.findtext("a") == "aaa")


def test_root_node_frontik_attribute():
    with frontik_debug.get_page_xml("test_app/simple_xml") as xml:
        assert(xml.get("frontik") == "true")
        assert(xml.find("doc").get("frontik", None) is None)


def test_fib0():
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/fib/?port={0}&n=0".format(srv_port)).read())
        # 0 1 2 3 4 5 6
        # 1 1 2 3 5 8 13
        assert(int(xml.text) == 1)


def test_fib2():
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/fib/?port={0}&n=2".format(srv_port)).read())
        # 0 1 2 3 4 5 6
        # 1 1 2 3 5 8 13
        assert(int(xml.text) == 2)


def test_fib6():
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/fib/?port={0}&n=6".format(srv_port)).read())
        # 0 1 2 3 4 5 6
        # 1 1 2 3 5 8 13
        assert(int(xml.text) == 13)


def test_timeout():
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/long_page_request/?port={0}".format(srv_port)).read())

        assert(xml.text == "error")

        time.sleep(2)

def test_finishexception():
    with frontik_debug.instance() as srv_port:
        data = urllib2.urlopen("http://localhost:{0}/test_app/finish_page/".format(srv_port)).read()
        assert(data == "success")

def test_multi_app_simple():
    with frontik_debug.get_page_xml("test_app/use_lib") as xml:
        assert xml.text == "10"


def test_post_url_simple():
    '''
    simple post_page and post_url test
    '''
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/post_simple/?port={0}".format(srv_port)).read())
        assert (xml.text == "42")


def test_post_url_mfd():
    '''
    creating mfd request and url_post it
    '''
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/post_url/?port={0}".format(srv_port)).read())
        print xml.text
        assert("BAD" not in xml.text)

def test_error_in_cb():
    '''
    if parsing error with wrong json or xml we must send None into callback
    '''
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/bad_page/?port={0}".format(srv_port)).read())
        assert (xml.text == "4242")

def test_finish_with_401():
    '''
    exception with handlers
    '''
    with frontik_debug.instance() as srv_port:
        try:
            answer = urllib2.urlopen("http://localhost:{0}/test_app/finish_401/".format(srv_port))
            assert False
        except Exception as e:
            assert (e.msg == "Unauthorized" and e.code == 401
                    and e.headers["WWW-Authenticate"] == 'Basic realm="Secure Area"')


def test_exception_text():
    '''
    throwing exception with plaintext
    '''
    with frontik_debug.instance() as srv_port:
        answer = urllib2.urlopen("http://localhost:{0}/test_app/test_exception_text/?port={0}".format(srv_port)).read()
        assert(answer == "This is just a plain text")

def test_exception_xml_xsl():
    '''
    throwing exception with xml and xsl
    '''
    with frontik_debug.instance() as srv_port:
        html = urllib2.urlopen("http://localhost:{0}/test_app/test_exception_xml_xsl".format(srv_port)).read()
        assert (html == "<html><body><h1>ok</h1></body></html>\n")


if __name__ == "__main__":
    nose.main()

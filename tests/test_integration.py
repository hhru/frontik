# coding=utf-8

import urllib2

from lxml import etree
import nose

from integration_util import FrontikTestInstance

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
    try:
        with frontik_debug.get_page('inexistent_page') as response:
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


def test_job_fail():
    # this test became bizarre because of Firefox browser, see handler_debug.py
    with frontik_debug.instance() as srv_port:
        try:
            urllib2.urlopen('http://localhost:{0}/test_app/job_fail'.format(srv_port)).info()
            raise Exception("get_page should`ve failed with HTTPError 400")
        except urllib2.HTTPError, e:
            assert(e.code == 400)

        ok = urllib2.urlopen('http://localhost:{0}/test_app/job_fail?nofail=True'.format(srv_port))
        assert(ok.read().find("ok") is not None)


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


def test_multi_app_simple():
    with frontik_debug.get_page_xml("test_app/use_lib") as xml:
        assert xml.text == "10"


def test_post_url_simple():
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/post_simple/?port={0}".format(srv_port)).read())
        assert (xml.text == "42")


def test_post_url_mfd():
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/post_url/?port={0}".format(srv_port)).read())
        assert(xml.text is None)


def test_error_in_cb():
    """
    if parsing error with wrong json or xml we must send None into callback
    """
    with frontik_debug.instance() as srv_port:
        xml = etree.fromstring(urllib2.urlopen("http://localhost:{0}/test_app/bad_page/?port={0}".format(srv_port)).read())
        assert (xml.text == "4242")


def test_check_finished():
    # Get the page for the first time

    with frontik_debug.get_page_text('test_app/check_finished') as text:
        assert text == ''

    # And check that callback has not been called

    with frontik_debug.get_page_text('test_app/check_finished') as text:
        assert text == ''

if __name__ == "__main__":
    nose.main()

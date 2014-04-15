import unittest
import urllib2

from lxml import etree

from integration_util import FrontikTestInstance

frontik_debug = FrontikTestInstance('./tests/projects/frontik.cfg')


class TestXsl(unittest.TestCase):
    def xsl_transformation_test(self):
        with frontik_debug.get_page_xml('test_app/simple') as html:
            self.assertEquals(etree.tostring(html), '<html><body><h1>ok</h1></body></html>')

    def test_content_type_with_xsl(self):
        with frontik_debug.get_page('test_app/simple') as response:
            assert(response.headers['content-type'].startswith('text/html'))

    def test_xsl_fail(self):
        with frontik_debug.instance() as srv_port:
            try:
                urllib2.urlopen('http://localhost:{0}/test_app/xsl_fail'.format(srv_port)).info()
                self.fail('get_page should fail with HTTPError 500')
            except urllib2.HTTPError, e:
                self.assertTrue(any(map(lambda x: 'XSLTApplyError' in x, e.readlines())))
                self.assertEquals(e.code, 500)

    def test_xsl_parse_fail(self):
        with frontik_debug.instance() as srv_port:
            try:
                urllib2.urlopen('http://localhost:{0}/test_app/xsl_parse_fail'.format(srv_port)).info()
                self.fail('get_page should fail with HTTPError 500')
            except urllib2.HTTPError, e:
                self.assertTrue(any(map(lambda x: 'XSLTParseError' in x, e.readlines())))
                self.assertEquals(e.code, 500)

    def test_content_type_wo_xsl(self):
        with frontik_debug.get_page('test_app/simple', notpl=True) as response:
            self.assertTrue(response.headers['content-type'].startswith('application/xml'))

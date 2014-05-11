# coding=utf-8

import unittest

from lxml import etree

from tests.instances import frontik_debug


class TestXsl(unittest.TestCase):
    def test_xsl_transformation(self):
        html = frontik_debug.get_page_xml('test_app/simple')
        self.assertEquals(etree.tostring(html), '<html><body><h1>ok</h1></body></html>')

    def test_content_type_with_xsl(self):
        response = frontik_debug.get_page('test_app/simple')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))

    def test_xsl_fail(self):
        response = frontik_debug.get_page('test_app/xsl_fail')
        self.assertEquals(response.status_code, 500)

        html = frontik_debug.get_page_text('test_app/xsl_fail?debug')
        self.assertTrue('XSLTApplyError' in html)

    def test_xsl_parse_fail(self):
        response = frontik_debug.get_page('test_app/xsl_parse_fail')
        self.assertEquals(response.status_code, 500)

        html = frontik_debug.get_page_text('test_app/xsl_parse_fail?debug')
        self.assertTrue('XSLTParseError' in html)

    def test_content_type_wo_xsl(self):
        response = frontik_debug.get_page('test_app/simple', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/xml'))

    def test_cdata(self):
        html = frontik_debug.get_page_text('test_app/cdata/?port={port}')
        self.assertIsNotNone(html.find('test'))
        self.assertIsNotNone(html.find('CDATA'))

    def test_xml_include(self):
        xml = frontik_debug.get_page_xml('test_app/include_xml')
        self.assertEquals(xml.findtext('a'), 'aaa')

    def test_root_node_frontik_attribute(self):
        xml = frontik_debug.get_page_xml('test_app/simple_xml')
        self.assertEquals(xml.get('frontik'), 'true')
        self.assertIsNone(xml.find('doc').get('frontik', None))

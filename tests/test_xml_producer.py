# coding=utf-8

import unittest

from .instances import frontik_debug


class TestXsl(unittest.TestCase):
    def test_xsl_transformation(self):
        response = frontik_debug.get_page('test_app/simple')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, '<html><body><h1>ok</h1></body></html>\n')

    def test_xsl_fail(self):
        response = frontik_debug.get_page('test_app/xsl_fail')
        self.assertEqual(response.status_code, 500)

        html = frontik_debug.get_page_text('test_app/xsl_fail?debug')
        self.assertTrue('XSLTApplyError' in html)

    def test_xsl_parse_fail(self):
        response = frontik_debug.get_page('test_app/xsl_parse_fail')
        self.assertEqual(response.status_code, 500)

        html = frontik_debug.get_page_text('test_app/xsl_parse_fail?debug')
        self.assertIn('XSLTParseError', html)

    def test_no_xsl_template(self):
        response = frontik_debug.get_page('test_app/simple?template=no.xsl')
        self.assertEquals(response.status_code, 500)

        html = frontik_debug.get_page_text('test_app/simple?template=no.xsl&debug')
        self.assertIn('IOError: Error reading file', html)

    def test_no_xsl_mode(self):
        response = frontik_debug.get_page('test_app/simple', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/xml'))

    def test_cdata(self):
        html = frontik_debug.get_page_text('test_app/cdata/?port={port}')
        self.assertIsNotNone(html.find('test'))
        self.assertIsNotNone(html.find('CDATA'))

    def test_xml_include(self):
        xml = frontik_debug.get_page_xml('test_app/include_xml')
        self.assertEqual(xml.findtext('a'), 'aaa')

    def test_root_node_frontik_attribute(self):
        xml = frontik_debug.get_page_xml('test_app/simple_xml')
        self.assertEqual(xml.get('frontik'), 'true')
        self.assertIsNone(xml.find('doc').get('frontik', None))

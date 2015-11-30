# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestXsl(unittest.TestCase):
    def test_xsl_transformation(self):
        response = frontik_test_app.get_page('xsl/simple')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, '<html><body><h1>ok</h1></body></html>\n')

    def test_xsl_apply_error(self):
        response = frontik_test_app.get_page('xsl/apply_error')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/apply_error?debug')
        self.assertIn('XSLT ERROR in file', html)

    def test_xsl_parse_error(self):
        response = frontik_test_app.get_page('xsl/parse_error')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/parse_error?debug')
        self.assertIn('failed parsing XSL file parse_error.xsl (XSL parse error)', html)

    def test_xsl_syntax_error(self):
        response = frontik_test_app.get_page('xsl/syntax_error')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/syntax_error?debug')
        self.assertIn('failed parsing XSL file syntax_error.xsl (XML syntax)', html)

    def test_no_xsl_template(self):
        response = frontik_test_app.get_page('xsl/simple?template=no.xsl')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/simple?template=no.xsl&debug')
        self.assertIn('failed loading XSL file no.xsl', html)

    def test_no_xsl_mode(self):
        response = frontik_test_app.get_page('xsl/simple', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/xml'))

    def test_cdata(self):
        html = frontik_test_app.get_page_text('cdata')
        self.assertIsNotNone(html.find('test'))
        self.assertIsNotNone(html.find('CDATA'))

    def test_xml_include(self):
        xml = frontik_test_app.get_page_xml('include_xml')
        self.assertEqual(xml.findtext('a'), 'aaa')

    def test_root_node_frontik_attribute(self):
        xml = frontik_test_app.get_page_xml('simple_xml')
        self.assertEqual(xml.get('frontik'), 'true')
        self.assertIsNone(xml.find('doc').get('frontik', None))

import unittest

from tests.instances import frontik_test_app


class TestXsl(unittest.TestCase):
    def test_xsl_transformation(self):
        response = frontik_test_app.get_page('xsl/simple')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, b'<html><body><h1>ok</h1></body></html>\n')

    def test_xsl_transformation_async(self):
        response = frontik_test_app.get_page('xsl/simple_async')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, b'<html><body><h1>ok</h1></body></html>\n')

    def test_xsl_apply_error(self):
        response = frontik_test_app.get_page('xsl/apply_error')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/apply_error?debug')
        self.assertIn('XSLT ERROR in file', html)

    def test_xsl_apply_error_async(self):
        response = frontik_test_app.get_page('xsl/apply_error_async')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/apply_error_async?debug')
        self.assertIn('XSLT ERROR in file', html)

    def test_xsl_parse_error(self):
        response = frontik_test_app.get_page('xsl/parse_error')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/parse_error?debug')
        self.assertIn('failed parsing XSL file parse_error.xsl (XSL parse error)', html)

    def test_xsl_parse_error_async(self):
        response = frontik_test_app.get_page('xsl/parse_error_async')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/parse_error_async?debug')
        self.assertIn('failed parsing XSL file parse_error.xsl (XSL parse error)', html)

    def test_xsl_syntax_error(self):
        response = frontik_test_app.get_page('xsl/syntax_error')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/syntax_error?debug')
        self.assertIn('failed parsing XSL file syntax_error.xsl (XML syntax)', html)

    def test_xsl_syntax_error_async(self):
        response = frontik_test_app.get_page('xsl/syntax_error_async')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/syntax_error_async?debug')
        self.assertIn('failed parsing XSL file syntax_error.xsl (XML syntax)', html)

    def test_no_xsl_template(self):
        response = frontik_test_app.get_page('xsl/simple?template=no.xsl')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/simple?template=no.xsl&debug')
        self.assertIn('failed loading XSL file no.xsl', html)

    def test_no_xsl_template_async(self):
        response = frontik_test_app.get_page('xsl/simple_async?template=no.xsl')
        self.assertEqual(response.status_code, 500)

        html = frontik_test_app.get_page_text('xsl/simple_async?template=no.xsl&debug')
        self.assertIn('failed loading XSL file no.xsl', html)

    def test_no_xsl_mode(self):
        response = frontik_test_app.get_page('xsl/simple', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/xml'))

    def test_no_xsl_mode_async(self):
        response = frontik_test_app.get_page('xsl/simple_async', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/xml'))

    def test_cdata(self):
        html = frontik_test_app.get_page_text('cdata')
        self.assertIn('test', html)
        self.assertIn('CDATA', html)

    def test_cdata_async(self):
        html = frontik_test_app.get_page_text('cdata_async')
        self.assertIn('test', html)
        self.assertIn('CDATA', html)

    def test_xml_include(self):
        xml = frontik_test_app.get_page_xml('include_xml')
        self.assertEqual(xml.findtext('a'), 'aaa')

    def test_xml_include_async(self):
        xml = frontik_test_app.get_page_xml('include_xml_async')
        self.assertEqual(xml.findtext('a'), 'aaa')

    def test_root_node_frontik_attribute(self):
        xml = frontik_test_app.get_page_xml('simple_xml')
        self.assertEqual(xml.find('element').get('name'), 'Test element')
        self.assertIsNone(xml.find('doc').get('frontik', None))

    def test_root_node_frontik_attribute_async(self):
        xml = frontik_test_app.get_page_xml('simple_xml_async')
        self.assertEqual(xml.find('element').get('name'), 'Test element')
        self.assertIsNone(xml.find('doc').get('frontik', None))

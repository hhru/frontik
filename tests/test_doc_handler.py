import unittest

from lxml_asserts.testcase import LxmlTestCaseMixin

from .instances import frontik_test_app


class TestDoc(unittest.TestCase, LxmlTestCaseMixin):
    def test_doc_page(self):
        xml = frontik_test_app.get_page_xml('compose_doc')

        self.assertIsNotNone(xml.find('a'))
        self.assertEqual(xml.findtext('a'), 'aaa')

        self.assertIsNotNone(xml.find('bbb'))

        self.assertIsNotNone(xml.find('c'))
        self.assertIn(xml.findtext('c'), (None, ''))

    def test_doc_page_async(self):
        xml = frontik_test_app.get_page_xml('compose_doc_async')

        self.assertIsNotNone(xml.find('a'))
        self.assertEqual(xml.findtext('a'), 'aaa')

        self.assertIsNotNone(xml.find('bbb'))

        self.assertIsNotNone(xml.find('c'))
        self.assertIn(xml.findtext('c'), (None, ''))

    def test_doc_invalid_xml(self):
        xml = frontik_test_app.get_page_xml('compose_doc?invalid=true')

        self.assertIsNotNone(xml.find('error'))
        self.assertEqual(xml.find('error').get('reason'), 'invalid xml')

    def test_doc_invalid_xml_async(self):
        xml = frontik_test_app.get_page_xml('compose_doc_async?invalid=true')

        self.assertIsNotNone(xml.find('error'))
        self.assertEqual(xml.find('error').get('reason'), 'invalid xml')

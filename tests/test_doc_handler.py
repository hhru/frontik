# coding=utf-8

import unittest

from frontik.testing.xml_asserts import XmlTestCaseMixin

from .instances import frontik_test_app


class TestDoc(unittest.TestCase, XmlTestCaseMixin):
    def test_doc_page(self):
        xml = frontik_test_app.get_page_xml('compose_doc')

        self.assertIsNotNone(xml.find('a'))
        self.assertEqual(xml.findtext('a'), 'aaa')

        self.assertIsNotNone(xml.find('bbb'))

        self.assertIsNotNone(xml.find('c'))
        self.assertIn(xml.findtext('c'), (None, ''))

    def test_doc_invalid_xml(self):
        xml = frontik_test_app.get_page_xml('compose_doc?invalid=true')

        self.assertIsNotNone(xml.find('error'))
        self.assertEqual(xml.find('error').get('reason'), 'invalid XML')

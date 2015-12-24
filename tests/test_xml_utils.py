# coding=utf-8

import os.path
import unittest

from lxml import etree
from lxml_asserts.testcase import LxmlTestCaseMixin

from frontik.xml_util import dict_to_xml, xml_from_file, xml_to_dict

XML = etree.XML('''
    <root>
        <key1>value</key1>
        <key2></key2>
        <nested>
            <key1>русский текст в utf-8</key1>
            <key2>русский текст в unicode</key2>
        </nested>
        <complexNested>
            <nested>
                <key>value</key>
                <otherKey>otherValue</otherKey>
            </nested>
            <int>123</int>
            <bool>True</bool>
        </complexNested>
    </root>
    ''')

DICT_BEFORE = {
    'key1': 'value',
    'key2': '',
    'nested': {
        'key1': 'русский текст в utf-8',
        'key2': u'русский текст в unicode'
    },
    'complexNested': {
        'nested': {
            'key': 'value',
            'otherKey': 'otherValue'
        },
        'int': 123,
        'bool': True
    }
}

DICT_AFTER = {
    'key1': 'value',
    'key2': '',
    'nested': {
        'key1': u'русский текст в utf-8',
        'key2': u'русский текст в unicode'
    },
    'complexNested': {
        'nested': {
            'key': 'value',
            'otherKey': 'otherValue'
        },
        'int': '123',
        'bool': 'True'
    }
}


class TestXmlUtils(unittest.TestCase, LxmlTestCaseMixin):
    def test_xml_to_dict_and_back_again(self):
        self.assertEqual(xml_to_dict(XML), DICT_AFTER)
        self.assertXmlEqual(dict_to_xml(DICT_BEFORE, 'root'), XML)

        self.assertEqual(xml_to_dict(dict_to_xml(DICT_BEFORE, 'root')), DICT_AFTER)
        self.assertXmlEqual(dict_to_xml(xml_to_dict(XML), 'root'), XML)

    XML_FILE = os.path.join(os.path.dirname(__file__), 'projects', 'test_app', 'xml', 'aaa.xml')
    XML_MISSING_FILE = os.path.join(os.path.dirname(__file__), 'bbb.xml')
    XML_SYNTAX_ERROR_FILE = os.path.join(os.path.dirname(__file__), 'projects', 'test_app', 'xsl', 'syntax_error.xsl')

    class MockLog(object):
        def __init__(self):
            self.message = None

        def error(self, message, *args):
            self.message = message % args

    def test_xml_from_file(self):
        result = xml_from_file(self.XML_FILE, TestXmlUtils.MockLog())
        self.assertIn('Source:', result[0].text)
        self.assertEqual(result[1].text, 'aaa')

    def test_xml_from_file_does_not_exist(self):
        log = TestXmlUtils.MockLog()

        with self.assertRaises(IOError):
            xml_from_file(self.XML_MISSING_FILE, log)

        self.assertIn('failed to read xml file', log.message)

    def test_xml_from_file_syntax_error(self):
        log = TestXmlUtils.MockLog()

        with self.assertRaises(etree.XMLSyntaxError):
            xml_from_file(self.XML_SYNTAX_ERROR_FILE, log)

        self.assertIn('failed to parse xml file', log.message)

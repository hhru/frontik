import os.path
import unittest

from lxml import etree
from lxml_asserts.testcase import LxmlTestCaseMixin
from tornado.testing import ExpectLog

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
        'key2': 'русский текст в unicode'
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
        'key1': 'русский текст в utf-8',
        'key2': 'русский текст в unicode'
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

    def test_xml_from_file(self):
        result = xml_from_file(self.XML_FILE)
        self.assertEqual(result.text, 'aaa')

    def test_xml_from_file_does_not_exist(self):
        with self.assertRaises(IOError):
            with ExpectLog('frontik.xml_util', "failed to read xml file.*"):
                xml_from_file(self.XML_MISSING_FILE)

    def test_xml_from_file_syntax_error(self):
        with self.assertRaises(etree.XMLSyntaxError):
            with ExpectLog('frontik.xml_util', "failed to parse xml file.*"):
                xml_from_file(self.XML_SYNTAX_ERROR_FILE)

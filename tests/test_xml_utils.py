# coding=utf-8

import unittest

from lxml import etree
from lxml_asserts.testcase import LxmlTestCaseMixin

from frontik.xml_util import xml_to_dict, dict_to_xml

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

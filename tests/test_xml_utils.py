# coding=utf-8

import unittest

import lxml.etree as etree

from frontik.xml_util import xml_to_dict, dict_to_xml

xml = '''
    <root>
        <key1>value</key1>
        <key2></key2>
        <nested>
            <key>русский текст</key>
        </nested>
        <complexNested>
            <nested>
                <key>value</key>
                <otherKey>otherValue</otherKey>
            </nested>
            <other>123</other>
        </complexNested>
    </root>
    '''

dictionary_before = {
    'key1': 'value',
    'key2': '',
    'nested': {
        'key': 'русский текст'
    },
    'complexNested': {
        'nested': {
            'key': 'value',
            'otherKey': 'otherValue'
        },
        'other': 123
    }
}

dictionary_after = {
    'key1': 'value',
    'key2': '',
    'nested': {
        'key': '&#1088;&#1091;&#1089;&#1089;&#1082;&#1080;&#1081; &#1090;&#1077;&#1082;&#1089;&#1090;'
    },
    'complexNested': {
        'nested': {
            'key': 'value',
            'otherKey': 'otherValue'
        },
        'other': '123'
    }
}


class TestXmlUtils(unittest.TestCase):
    def test_xml_to_dict_and_back_again(self):
        self.assertEquals(xml_to_dict(etree.XML(xml)), dictionary_after)
        self.assertEquals(xml_to_dict(dict_to_xml(dictionary_before, 'root')), dictionary_after)

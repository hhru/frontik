# coding=utf-8

from frontik.testing.xml_asserts import _xml_compare, XmlTestCaseMixin

XmlResponseTestCaseMixin = XmlTestCaseMixin  # Deprecated alias
xml_compare = _xml_compare  # Deprecated alias, use XmlTestCaseMixin.assert* methods

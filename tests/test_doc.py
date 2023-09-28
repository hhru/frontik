import unittest

from lxml import etree
from lxml_asserts.testcase import LxmlTestCaseMixin
from tornado.concurrent import Future
from http_client.request_response import DataParseError, RequestResult

from frontik.doc import Doc


class TestDoc(unittest.TestCase, LxmlTestCaseMixin):
    def test_simple(self) -> None:
        d = Doc('a')

        self.assertTrue(d.is_empty())

        d.put(None)

        self.assertXmlEqual(d.to_etree_element(), b'<a/>')

        node = etree.Element('b')
        node.text = 'тест'
        d.put(node)

        self.assertFalse(d.is_empty())
        self.assertXmlEqual(
            d.to_etree_element(),
            b"""<?xml version='1.0' encoding='utf-8'?>\n<a><b>\xd1\x82\xd0\xb5\xd1\x81\xd1\x82</b></a>""",
        )

    async def test_future_simple(self):
        d = Doc('a')
        f: Future = Future()
        d.put(f)

        self.assertXmlEqual(d.to_etree_element(), b"""<?xml version='1.0' encoding='utf-8'?>\n<a/>""")

        f.set_result(etree.Element('test'))

        self.assertXmlEqual(d.to_etree_element(), b"""<?xml version='1.0' encoding='utf-8'?>\n<a><test/></a>""")

    async def test_future_etree_element(self):
        d = Doc('a')
        f: Future = Future()
        f.set_result(etree.Element('b'))
        d.put(f)

        self.assertXmlEqual(d.to_etree_element(), b"""<?xml version='1.0' encoding='utf-8'?>\n<a><b/></a>""")

    async def test_future_list(self):
        d = Doc('a')
        f: Future = Future()
        f.set_result([etree.Comment('ccc'), etree.Element('bbb')])
        d.put(f)

        self.assertXmlEqual(d.to_etree_element(), """<?xml version='1.0'?>\n<a><!--ccc--><bbb/></a>""")

    async def test_failed_future(self):
        d = Doc('a')
        f: Future = Future()
        result = self.get_test_request_result()
        result._data_parse_error = DataParseError(reason='error', code='code')
        f.set_result(result)
        d.put(f)

        self.assertXmlEqual(
            d.to_etree_element(), """<?xml version='1.0'?>\n<a><error reason="error" code="code"/></a>"""
        )

    async def test_future_string_value(self):
        d = Doc('a')
        f: Future = Future()
        result = self.get_test_request_result()
        result._content_type = 'text'
        result._data = 'plain_text'
        f.set_result(result)
        d.put(f)

        self.assertXmlEqual(d.to_etree_element(), """<?xml version='1.0'?>\n<a></a>""")

    def test_doc_nested(self) -> None:
        a = Doc('a')
        b = Doc('b')
        a.put(b)

        self.assertXmlEqual(a.to_etree_element(), b"""<?xml version='1.0' encoding='utf-8'?>\n<a><b/></a>""")

    def test_serializable(self) -> None:
        class Serializable:
            def __init__(self, tag: str, value: str) -> None:
                self.tag = tag
                self.value = value

            def to_etree_element(self):
                result = etree.Element(self.tag)
                result.text = self.value
                return result

        a = Doc('a')
        a.put(Serializable('testNode', 'vally'))

        self.assertEqual(
            a.to_string(), b"""<?xml version='1.0' encoding='utf-8'?>\n<a><testNode>vally</testNode></a>"""
        )

    def test_other_types(self) -> None:
        a = Doc('a')
        a.put('1')

        self.assertRaises(ValueError, a.to_string)

    def test_root_node(self) -> None:
        d = Doc(root_node=etree.Element('doc'))
        d.put(etree.Element('test1'))

        self.assertXmlEqual(d.to_etree_element(), b"""<?xml version='1.0' encoding='utf-8'?>\n<doc><test1/></doc>""")

    def test_root_node_doc(self) -> None:
        d1 = Doc('a')
        d1.put(etree.Comment('1'))

        d2 = Doc(root_node=d1)
        d2.put(etree.Comment('2'))

        self.assertXmlEqual(
            d2.to_etree_element(), b"""<?xml version='1.0' encoding='utf-8'?>\n<a><!--1--><!--2--></a>"""
        )

    def test_string_as_root_node(self) -> None:
        d = Doc(root_node='a')
        self.assertXmlEqual(d.to_etree_element(), b"""<?xml version='1.0' encoding='utf-8'?>\n<a></a>""")

    def test_root_node_invalid(self) -> None:
        self.assertRaises(TypeError, Doc, root_node=etree.Comment('invalid root doc'))

    @staticmethod
    def get_test_request_result() -> RequestResult:
        class FakeRequest:
            name = 'name'

        return RequestResult(FakeRequest(), None, None, False, False)

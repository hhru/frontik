# coding=utf-8

from lxml import etree
from lxml.builder import E
import unittest
from functools import partial

import frontik.doc
from frontik.future import Placeholder


class TestDoc(unittest.TestCase):
    def test_simple(self):
        d = frontik.doc.Doc('a')

        self.assertTrue(d.is_empty())

        d.put('test')

        self.assertFalse(d.is_empty())
        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a>test</a>""")

    def test_placeholder_simple(self):
        d = frontik.doc.Doc('a')
        p = Placeholder()
        d.put(p)

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a/>""")

        p.set_data('test')

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a>test</a>""")

    def test_placeholder_etree_element(self):
        d = frontik.doc.Doc('a')
        p = Placeholder()
        p.set_data(etree.Element('b'))
        d.put(p)

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a><b/></a>""")

    def test_placeholder_list(self):
        d = frontik.doc.Doc('a')
        p = Placeholder()
        p.set_data([etree.Comment('ccc'), etree.Element('bbb')])
        d.put(p)

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a><!--ccc--><bbb/></a>""")

    def test_failed_future(self):
        d = frontik.doc.Doc('a')
        p = Placeholder()
        p.set_data(frontik.future.FailedFutureException(effective_url='url', error='error', code='code', body='body'))
        d.put(p)

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n"""
                                        """<a><error reason="error" code="code"><!--body--></error></a>""")

    def test_doc_nested(self):
        a = frontik.doc.Doc('a')
        b = frontik.doc.Doc('b')
        b.put('test')
        a.put(b)

        self.assertEqual(a.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a><b>test</b></a>""")

    def test_nodes_and_text(self):
        a = frontik.doc.Doc('a')
        a.put('1')
        a.put(frontik.doc.Doc('b'))
        a.put('2')
        a.put(frontik.doc.Doc('c'))
        a.put('3')

        self.assertEqual(a.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a>1<b/>2<c/>3</a>""")

    def test_root_node(self):
        d = frontik.doc.Doc(root_node=etree.Element('doc'))
        d.put(etree.Element('test1'))

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<doc><test1/></doc>""")

if __name__ == '__main__':
    unittest.main()

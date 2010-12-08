import unittest

import frontik.doc
import frontik.future

class MockFuture(frontik.future.FutureVal):
    def __init__(self, data):
        self.data = data

    def get(self):
        return self.data

class TestDoc(unittest.TestCase):
    def test_simple(self):
        d = frontik.doc.Doc("a")
        d.put("111")

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a>111</a>""")

    def test_future_simple(self):
        d = frontik.doc.Doc("a")
        d.put(MockFuture("111"))

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a>111</a>""")

    def test_future_return_node(self):
        d = frontik.doc.Doc("a")
        d.put(MockFuture(frontik.etree.Element("b")))

        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a><b/></a>""")

    def test_future_return_some_nodes(self):
        d = frontik.doc.Doc("a")
        d.put(MockFuture([frontik.etree.Comment("ccc"),
                          frontik.etree.Element("bbb")]))
        
        self.assertEqual(d.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a><!--ccc--><bbb/></a>""")

    def test_doc(self):
        a = frontik.doc.Doc("a")
        b = frontik.doc.Doc("b")

        b.put("1")

        a.put(b)

        self.assertEqual(a.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a><b>1</b></a>""")

    def test_nodes_and_text(self):
        a = frontik.doc.Doc("a")

	a.put("1")
	a.put(frontik.doc.Doc("b"))
	a.put("2")
	a.put(frontik.doc.Doc("c"))
	a.put("3")

        self.assertEqual(a.to_string(), """<?xml version='1.0' encoding='utf-8'?>\n<a>1<b/>2<c/>3</a>""")


if __name__ == "__main__":
    unittest.main()

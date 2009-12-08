import unittest

import frontik

class MockFuture(frontik.future.FutureVal):
    def __init__(self, data):
        self.data = data

    def get(self):
        return self.data

class TestDoc(unittest.TestCase):
    def test_simple(self):
        d = frontik.Doc('a')
        d.put('111')

        self.assertEqual(d.to_string(), '<a>111</a>')

    def test_future_simple(self):
        d = frontik.Doc('a')
        d.put(MockFuture('111'))

        self.assertEqual(d.to_string(), '<a>111</a>')

    def test_future_return_node(self):
        d = frontik.Doc('a')
        d.put(MockFuture(frontik.etree.Element('b')))

        self.assertEqual(d.to_string(), '<a><b/></a>')

    def test_future_return_some_nodes(self):
        d = frontik.Doc('a')
        d.put(MockFuture([frontik.etree.Comment('ccc'),
                          frontik.etree.Element('bbb')]))
        
        self.assertEqual(d.to_string(), '<a><!--ccc--><bbb/></a>')

    def test_doc(self):
        a = frontik.Doc('a')
        b = frontik.Doc('b')

        b.put('1')

        a.put(b)

        self.assertEqual(a.to_string(), '<a><b>1</b></a>')

if __name__ == '__main__':
    unittest.main()

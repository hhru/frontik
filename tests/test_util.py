# coding=utf-8

import unittest
from collections import OrderedDict

from tornado.escape import to_unicode
from tornado.httputil import HTTPFile, parse_body_arguments

from frontik.util import any_to_bytes, any_to_unicode, make_mfd, make_qs, make_url


class TestUtil(unittest.TestCase):
    def test_make_qs_simple(self):
        query_args = {'a': '1', 'b': '2'}
        self.assertQueriesEqual(make_qs(query_args), 'a=1&b=2')

    def test_make_qs_not_str(self):
        query_args = {'a': 1, 'b': 2.0, 'c': True}
        self.assertQueriesEqual(make_qs(query_args), 'a=1&b=2.0&c=True')

    def test_make_qs_iterables(self):
        query_args = {'a': [1, 2], 'b': {1, 2}, 'c': (1, 2), 'd': frozenset((1, 2))}
        self.assertQueriesEqual(make_qs(query_args), 'a=1&a=2&b=1&b=2&c=1&c=2&d=1&d=2')

    def test_make_qs_none(self):
        query_args = {'a': None, 'b': None}
        self.assertQueriesEqual(make_qs(query_args), '')

    def test_make_qs_encode(self):
        query_args = {'a': u'тест', 'b': 'тест'}
        qs = make_qs(query_args)
        self.assertIsInstance(qs, str)
        self.assertQueriesEqual(qs, 'a=%D1%82%D0%B5%D1%81%D1%82&b=%D1%82%D0%B5%D1%81%D1%82')

    def test_make_qs_from_ordered_dict(self):
        qs = make_qs(OrderedDict([('z', 'я'), ('г', 'd'), ('b', ['2', '1'])]))
        self.assertIsInstance(qs, str)
        self.assertEqual(qs, 'z=%D1%8F&%D0%B3=d&b=2&b=1')

    def test_make_qs_unicode_params(self):
        self.assertQueriesEqual(
            make_qs({'при': 'вет', u'по': u'ка'}),
            '%D0%BF%D1%80%D0%B8=%D0%B2%D0%B5%D1%82&%D0%BF%D0%BE=%D0%BA%D0%B0'
        )

    def test_make_url(self):
        self.assertEqual(
            make_url('http://test.com/path', param='value'),
            'http://test.com/path?param=value'
        )

        self.assertEqual(
            make_url('http://test.com/path?k=v', param='value'),
            'http://test.com/path?k=v&param=value'
        )

        self.assertEqual(
            make_url(u'http://тест.рф/path?k=v', param=u'тест'),
            u'http://тест.рф/path?k=v&param=%D1%82%D0%B5%D1%81%D1%82'
        )

    def assertQueriesEqual(self, qs1, qs2):
        qs1_list = sorted(qs1.split('&'))
        qs2_list = sorted(qs2.split('&'))
        self.assertEqual(qs1_list, qs2_list)

    def test_any_to_unicode(self):
        self.assertEqual(any_to_unicode(5), u'5')
        self.assertEqual(any_to_unicode(None), u'None')
        self.assertEqual(any_to_unicode(u'тест'), u'тест')
        self.assertEqual(any_to_unicode(u'тест'.encode('utf-8')), u'тест')

    def test_any_to_bytes(self):
        self.assertEqual(any_to_bytes(5), b'5')
        self.assertEqual(any_to_bytes(None), b'None')
        self.assertEqual(any_to_bytes(u'тест'), u'тест'.encode('utf-8'))
        self.assertEqual(any_to_bytes(u'тест'.encode('utf-8')), u'тест'.encode('utf-8'))

    def test_make_mfd(self):
        args, files = {}, {}
        body, content_type = make_mfd(
            {
                'arg1': 'value1'
            },
            {
                'file0': [HTTPFile(filename='file0.rar', body='ARCHIVE', content_type='some/type\r\n\r\nBAD DATA')],
                'file1': [HTTPFile(filename='file1.png', body='CAT PICTURE', content_type='image/png')],
                'file2': [HTTPFile(filename='file2.txt', body='TEXT')],
                'file3': [
                    HTTPFile(filename=r'file3-"part1".unknown', body='BODY1'),
                    HTTPFile(filename=r'file3-\part2\.unknown', body='BODY2'),
                ],
            }
        )

        parse_body_arguments(to_unicode(content_type), body, args, files)

        self.assertEqual(args['arg1'], [b'value1'])

        self.assertEqual(files['file0'][0]['filename'], 'file0.rar')
        self.assertEqual(files['file0'][0]['body'], b'ARCHIVE')
        self.assertEqual(files['file0'][0]['content_type'], 'some/type    BAD DATA')

        self.assertEqual(files['file1'][0]['filename'], 'file1.png')
        self.assertEqual(files['file1'][0]['body'], b'CAT PICTURE')
        self.assertEqual(files['file1'][0]['content_type'], 'image/png')

        self.assertEqual(files['file2'][0]['filename'], 'file2.txt')
        self.assertEqual(files['file2'][0]['body'], b'TEXT')
        self.assertEqual(files['file2'][0]['content_type'], 'text/plain')

        self.assertEqual(files['file3'][0]['filename'], r'file3-"part1".unknown')
        self.assertEqual(files['file3'][0]['body'], b'BODY1')
        self.assertEqual(files['file3'][0]['content_type'], 'application/octet-stream')
        self.assertEqual(files['file3'][1]['filename'], r'file3-\part2\.unknown')
        self.assertEqual(files['file3'][1]['body'], b'BODY2')
        self.assertEqual(files['file3'][1]['content_type'], 'application/octet-stream')

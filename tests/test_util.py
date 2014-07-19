# coding=utf-8

import unittest

from frontik.util import make_qs


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
        self.assertQueriesEqual(make_qs(query_args), 'a=%D1%82%D0%B5%D1%81%D1%82&b=%D1%82%D0%B5%D1%81%D1%82')

    def assertQueriesEqual(self, qs1, qs2):
        qs1_list = sorted(qs1.split('&'))
        qs2_list = sorted(qs2.split('&'))
        self.assertEqual(qs1_list, qs2_list)

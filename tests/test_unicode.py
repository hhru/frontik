# coding=utf-8

import unittest

from tornado.escape import to_unicode

from frontik.util import make_url
from .instances import frontik_test_app


class TestUnicode(unittest.TestCase):
    def test_unicode_argument(self):
        response = frontik_test_app.get_page(make_url('arguments', param=u'тест'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(to_unicode(response.content), u'{"тест": "тест"}')

    def test_cp1251_argument(self):
        cp1251_arg = u'тест'.encode('cp1251')
        response = frontik_test_app.get_page(make_url('arguments', param=cp1251_arg))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(to_unicode(response.content), u'{"тест": "тест"}')

    def test_argument_with_invalid_chars(self):
        arg_with_invalid_chars = u'≤'.encode('koi8_r') + 'тест'
        response = frontik_test_app.get_page(make_url('arguments', param=arg_with_invalid_chars))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(to_unicode(response.content), u'{"тест": "тест"}')

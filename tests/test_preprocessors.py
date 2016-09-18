# coding=utf-8

import unittest

from requests.exceptions import Timeout

from .instances import frontik_test_app


class TestPreprocessors(unittest.TestCase):
    def test_preprocessors(self):
        response = frontik_test_app.get_page('preprocessors')
        self.assertEqual(response.content, b'1 2 3 (1 2 3 4) 5 6')
        self.assertEqual(response.headers['Content-Type'], 'text/plain')

    def test_preprocessors_nocallback(self):
        self.assertRaises(Timeout, lambda: frontik_test_app.get_page('preprocessors?nocallback=true', timeout=1))

    def test_preprocessors_fail(self):
        response = frontik_test_app.get_page('preprocessors?fail=true')
        self.assertEqual(response.status_code, 503)

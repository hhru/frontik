# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestPreprocessors(unittest.TestCase):
    def test_preprocessors(self):
        text = frontik_test_app.get_page_text('preprocessors')
        self.assertEqual(text, '1 2 3 4 5 6')

    def test_preprocessors_nocallback(self):
        text = frontik_test_app.get_page_text('preprocessors?nocallback=true')
        self.assertEqual(text, '1 2 3')

    def test_preprocessors_fail(self):
        response = frontik_test_app.get_page('preprocessors?fail=true')
        self.assertEqual(response.status_code, 503)

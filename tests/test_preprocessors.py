# coding=utf-8

import unittest

from . import py3_skip
from .instances import frontik_test_app


class TestPreprocessors(unittest.TestCase):
    @py3_skip
    def test_preprocessors(self):
        text = frontik_test_app.get_page_text('preprocessors')
        self.assertEqual(text, '1 2 3 4 5 6')

    @py3_skip
    def test_preprocessors_nocallback(self):
        text = frontik_test_app.get_page_text('preprocessors?nocallback=true')
        self.assertEqual(text, '1 2 3')

    @py3_skip
    def test_preprocessors_fail(self):
        response = frontik_test_app.get_page('preprocessors?fail=true')
        self.assertEqual(response.status_code, 503)

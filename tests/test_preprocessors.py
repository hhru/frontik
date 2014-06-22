# coding=utf-8

import unittest

from tests import frontik_debug


class TestPreprocessors(unittest.TestCase):
    def test_preprocessors(self):
        text = frontik_debug.get_page_text('test_app/preprocessors')
        self.assertEquals(text, '1 2 3 4 5 6')

    def test_preprocessors_nocallback(self):
        text = frontik_debug.get_page_text('test_app/preprocessors?nocallback=true')
        self.assertEquals(text, '1 2 3')

    def test_preprocessors_fail(self):
        response = frontik_debug.get_page('test_app/preprocessors?fail=true')
        self.assertEquals(response.status_code, 503)

# coding=utf-8

import unittest

from .instances import frontik_non_debug


class TestHandler(unittest.TestCase):
    def test_active_limit(self):
        text = frontik_non_debug.get_page_text('recursion?n=6')
        self.assertEqual(text, '200 200 200 200 200 503')

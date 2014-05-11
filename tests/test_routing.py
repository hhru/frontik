# coding=utf-8

import unittest

from tests.instances import frontik_debug


class TestRouting(unittest.TestCase):
    def test_regexp(self):
        html = frontik_debug.get_page_text('re_app/not_simple')
        self.assertIsNotNone(html.find('ok'))

    def test_simple_map2fs(self):
        html = frontik_debug.get_page_text('test_app/simple')
        self.assertIsNotNone(html.find('ok'))

    def test_fallback_map2fs(self):
        html = frontik_debug.get_page_text('re_app/simple')
        self.assertIsNotNone(html.find('ok'))

    def test_extra_slash_in_regex(self):
        """Routes specified with regexps should match precisely"""
        self.assertEquals(frontik_debug.get_page('re_app//not_simple').status_code, 404)

    def test_extra_slash_in_mapping(self):
        """Routes specified as mappings to filesystem can contain extra slashes"""
        self.assertEquals(frontik_debug.get_page('re_app//simple').status_code, 200)
        self.assertEquals(frontik_debug.get_page('test_app//nested///nested//////nested').status_code, 200)

    def test_rewrite(self):
        html = frontik_debug.get_page_text('re_app/id/some')
        self.assertIsNotNone(html.find('some'))

    def ids_rewrite_test(self):
        values = ('some', 'another')
        html = frontik_debug.get_page_text('re_app/id/{}'.format(','.join(values)))
        self.assertTrue(all(map(html.find, values)))

    def test_404(self):
        self.assertEquals(frontik_debug.get_page('inexistent_page').status_code, 404)

# coding=utf-8

import unittest

from .instances import frontik_re_app, frontik_test_app


class TestRouting(unittest.TestCase):
    def test_regexp(self):
        html = frontik_re_app.get_page_text('not_simple')
        self.assertIsNotNone(html.find('ok'))

    def test_file_mapping(self):
        html = frontik_test_app.get_page_text('simple')
        self.assertIsNotNone(html.find('ok'))

    def test_fallback_file_mapping(self):
        html = frontik_re_app.get_page_text('simple')
        self.assertIsNotNone(html.find('ok'))

    def test_extra_slash_in_regex(self):
        """Routes specified with regexps should match precisely"""
        self.assertEqual(frontik_re_app.get_page('//not_simple').status_code, 404)

    def test_extra_slash_in_mapping(self):
        """Routes specified as mappings to filesystem can contain extra slashes"""
        self.assertEqual(frontik_re_app.get_page('//simple').status_code, 200)
        self.assertEqual(frontik_test_app.get_page('//nested///nested//////nested').status_code, 200)

    def test_rewrite_single(self):
        html = frontik_re_app.get_page_text('id/some')
        self.assertIsNotNone(html.find('some'))

    def test_rewrite_multiple(self):
        values = ('some', 'another')
        html = frontik_re_app.get_page_text('id/{}'.format(','.join(values)))
        self.assertTrue(all(map(html.find, values)))

    def test_404(self):
        self.assertEqual(frontik_re_app.get_page('inexistent_page').status_code, 404)

    def test_no_page(self):
        self.assertEqual(frontik_test_app.get_page('no_page').status_code, 404)

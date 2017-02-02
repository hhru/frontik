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

    def test_preprocessors_new(self):
        response_json = frontik_test_app.get_page_json('preprocessors_new')
        self.assertEqual(
            response_json,
            {
                'run': ['pp1', 'pp2', 'pp3', 'oldstyle_pp', 'get_page'],
                'post': True
            }
        )

    def test_preprocessors_new_raise_finish(self):
        response_json = frontik_test_app.get_page_json('preprocessors_new?raise_finish=true')
        self.assertEqual(
            response_json,
            {
                'run': ['pp1', 'pp2', 'pp3'],
                'post': True
            }
        )

    def test_preprocessors_new_raise_error(self):
        response = frontik_test_app.get_page('preprocessors_new?raise_error=true')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'<html><title>400: Bad Request</title><body>400: Bad Request</body></html>')

# coding=utf-8

import unittest

from .instances import create_basic_auth_header, frontik_no_debug_app


class TestNonDebugMode(unittest.TestCase):
    def test_simple(self):
        html = frontik_no_debug_app.get_page_text('simple')
        self.assertIn('<h1>ok</h1>', html)

    def test_basic_auth_fail(self):
        response = frontik_no_debug_app.get_page('basic_auth')
        self.assertEqual(response.status_code, 401)

    def test_basic_auth_fail_on_wrong_pass(self):
        response = frontik_no_debug_app.get_page(
            'basic_auth', headers={'Authorization': create_basic_auth_header('user:bad')}
        )

        self.assertEqual(response.status_code, 401)

    def test_basic_auth_pass(self):
        response = frontik_no_debug_app.get_page(
            'basic_auth', headers={'Authorization': create_basic_auth_header('user:god')}
        )

        self.assertEqual(response.status_code, 200)

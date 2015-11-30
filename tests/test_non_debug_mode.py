# coding=utf-8

import unittest

from .instances import create_basic_auth_header, frontik_non_debug


class TestNonDebugMode(unittest.TestCase):
    def test_simple(self):
        html = frontik_non_debug.get_page_text('app/simple')
        self.assertIsNotNone(html.find('ok'))

    def test_basic_auth_fail(self):
        response = frontik_non_debug.get_page('app/basic_auth')
        self.assertEqual(response.status_code, 401)

    def test_basic_auth_fail_on_wrong_pass(self):
        response = frontik_non_debug.get_page(
            'app/basic_auth', headers={'Authorization': create_basic_auth_header('user:bad')}
        )

        self.assertEqual(response.status_code, 401)

    def test_basic_auth_pass(self):
        response = frontik_non_debug.get_page(
            'app/basic_auth', headers={'Authorization': create_basic_auth_header('user:god')}
        )

        self.assertEqual(response.status_code, 200)

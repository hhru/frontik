import unittest

from tests.instances import create_basic_auth_header, frontik_no_debug_app


class TestNonDebugMode(unittest.TestCase):
    def test_simple(self):
        html = frontik_no_debug_app.get_page_text('simple')
        self.assertIn('<h1>ok</h1>', html)

    def test_simple_async(self):
        html = frontik_no_debug_app.get_page_text('simple_async')
        self.assertIn('<h1>ok</h1>', html)

    def test_basic_auth_fail(self):
        response = frontik_no_debug_app.get_page('basic_auth')
        self.assertEqual(response.status_code, 401)

    def test_basic_auth_fail_async(self):
        response = frontik_no_debug_app.get_page('basic_auth_async')
        self.assertEqual(response.status_code, 401)

    def test_basic_auth_fail_on_wrong_pass(self):
        response = frontik_no_debug_app.get_page(
            'basic_auth', headers={'Authorization': create_basic_auth_header('user:bad')}
        )

        self.assertEqual(response.status_code, 401)

    def test_basic_auth_fail_on_wrong_pass_async(self):
        response = frontik_no_debug_app.get_page(
            'basic_auth_async', headers={'Authorization': create_basic_auth_header('user:bad')}
        )

        self.assertEqual(response.status_code, 401)

    def test_basic_auth_pass(self):
        response = frontik_no_debug_app.get_page(
            'basic_auth', headers={'Authorization': create_basic_auth_header('user:god')}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"authenticated": true}')

    def test_basic_auth_pass_async(self):
        response = frontik_no_debug_app.get_page(
            'basic_auth_async', headers={'Authorization': create_basic_auth_header('user:god')}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"authenticated": true}')

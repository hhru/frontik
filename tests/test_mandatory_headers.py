import unittest

from tests.instances import frontik_test_app


class TestPostprocessors(unittest.TestCase):
    def test_set_mandatory_headers(self):
        response = frontik_test_app.get_page('mandatory_headers?test_mandatory_headers')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers.get('TEST_HEADER'), 'TEST_HEADER_VALUE')
        self.assertEqual(response.cookies.get('TEST_COOKIE'), 'TEST_HEADER_COOKIE')

    def test_mandatory_headers_are_lost(self):
        response = frontik_test_app.get_page('mandatory_headers?test_without_mandatory_headers')
        self.assertEqual(response.status_code, 500)
        self.assertIsNone(response.headers.get('TEST_HEADER'))
        self.assertIsNone(response.headers.get('TEST_COOKIE'))

    def test_mandatory_headers_are_cleared(self):
        response = frontik_test_app.get_page('mandatory_headers?test_clear_set_mandatory_headers')
        self.assertEqual(response.status_code, 500)
        self.assertIsNone(response.headers.get('TEST_HEADER'))
        self.assertIsNone(response.headers.get('TEST_COOKIE'))

    def test_clear_not_set_headers_does_not_faile(self):
        response = frontik_test_app.get_page('mandatory_headers?test_clear_not_set_headers')
        self.assertEqual(response.status_code, 500)
        self.assertIsNone(response.headers.get('TEST_HEADER'))
        self.assertIsNone(response.headers.get('TEST_COOKIE'))

    def test_invalid_mandatory_cookie(self):
        response = frontik_test_app.get_page('mandatory_headers?test_invalid_mandatory_cookie')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers.get('TEST_COOKIE'), None)

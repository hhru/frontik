import unittest

from tests.instances import frontik_test_app


class TestHandler(unittest.TestCase):
    def test_error_in_yield(self) -> None:
        response = frontik_test_app.get_page('error_yield')
        self.assertEqual(response.status_code, 500)

    def test_error_in_yield_async(self) -> None:
        response = frontik_test_app.get_page('error_yield_async')
        self.assertEqual(response.status_code, 500)

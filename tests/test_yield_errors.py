import unittest

from .instances import frontik_test_app


class TestHandler(unittest.TestCase):
    def test_error_in_yield(self):
        response = frontik_test_app.get_page('error_yield')
        self.assertEqual(response.status_code, 500)

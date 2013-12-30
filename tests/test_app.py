import unittest

from .instances import frontik_broken_app


class TestApp(unittest.TestCase):
    def test_broken_app(self):
        self.assertRaises(AssertionError, frontik_broken_app.get_page, '')

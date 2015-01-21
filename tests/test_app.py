import unittest

from .instances import frontik_broken_app


class TestAppTestCase(unittest.TestCase):

    def test_broken_app(self):
        with self.assertRaises(AssertionError):
            frontik_broken_app.get_page('')

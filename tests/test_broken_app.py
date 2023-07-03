import unittest

from tests.instances import frontik_broken_config_app, frontik_broken_init_async_app


class TestBrokenApp(unittest.TestCase):
    def test_broken_config(self):
        self.assertRaises(AssertionError, frontik_broken_config_app.start)

    def test_broken_init_async(self):
        self.assertRaises(AssertionError, frontik_broken_init_async_app.start)

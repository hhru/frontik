# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestMicroHandler(unittest.TestCase):
    def test_simple(self):
        json = frontik_test_app.get_page_json('micro_handler')

        self.assertEqual(json['put']['error'], 'forbidden')
        self.assertEqual(json['post']['POST'], 'post')
        self.assertEqual(json['get']['GET'], 'get')
        self.assertEqual(json['delete'], None)

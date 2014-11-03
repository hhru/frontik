# coding=utf-8

import unittest

import requests

from .instances import frontik_test_app


class TestMicroHandler(unittest.TestCase):
    def test_simple(self):
        json = frontik_test_app.get_page_json('micro_handler')

        self.assertEqual(json['put']['error'], 'forbidden')
        self.assertEqual(json['post']['POST'], 'post')
        self.assertEqual(json['post']['get']['GET'], 'get')
        self.assertEqual(json['preprocessor'], True)
        self.assertEqual(json['delete'], None)

    def test_fail_on_error(self):
        response = frontik_test_app.get_page('micro_handler?fail_on_error=true')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, '{"fail_on_error": true}')

    def test_fail_on_error_default(self):
        response = frontik_test_app.get_page('micro_handler?fail_on_error=true&default=true')

        self.assertEqual(response.status_code, 401)

    def test_invalid_return_value(self):
        response = frontik_test_app.get_page('micro_handler?invalid_return_value=true', method=requests.delete)
        self.assertEqual(response.status_code, 500)

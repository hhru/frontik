# coding=utf-8

import unittest

import requests

from .instances import frontik_test_app


class TestMicroHandler(unittest.TestCase):
    def test_simple(self):
        json = frontik_test_app.get_page_json('micro_handler')

        self.assertEqual(json['put']['error'], 'forbidden')
        self.assertEqual(json['post'], {'POST': 'post'})
        self.assertEqual(json['preprocessor'], True)
        self.assertEqual(json['delete'], None)

    def test_fail_on_error(self):
        response = frontik_test_app.get_page('micro_handler?fail_on_error=true')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'{"fail_on_error": true}')

    def test_fail_on_error_without_done(self):
        response = frontik_test_app.get_page('micro_handler/fail_on_error_without_done')
        self.assertEqual(response.status_code, 403)

    def test_fail_on_error_default(self):
        response = frontik_test_app.get_page('micro_handler?fail_on_error_default=true&code=400', method=requests.post)
        self.assertEqual(response.status_code, 400)

        response = frontik_test_app.get_page('micro_handler?fail_on_error_default=true&code=500', method=requests.post)
        self.assertEqual(response.status_code, 502)

    def test_future(self):
        json = frontik_test_app.get_page_json('micro_handler/future')

        future_result = json['future']
        self.assertEqual(future_result, 'future_result')

    def test_future_fail(self):
        response = frontik_test_app.get_page('micro_handler/future?fail_future=true')
        self.assertEqual(response.status_code, 500)

    def test_future_with_unknown_result_fail_on_error(self):
        response = frontik_test_app.get_page('micro_handler/future?fail_on_error_future=true')
        self.assertEqual(response.status_code, 200)

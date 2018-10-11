import unittest

import requests

from .instances import frontik_test_app


class TestFailFast(unittest.TestCase):
    def test_simple(self):
        json = frontik_test_app.get_page_json('fail_fast')

        self.assertEqual(json['put']['error'], 'forbidden')
        self.assertEqual(json['post'], {'POST': 'post'})
        self.assertEqual(json['preprocessor'], True)
        self.assertEqual(json['delete'], None)

    def test_fail_fast(self):
        response = frontik_test_app.get_page('fail_fast?fail_fast=true')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'{"fail_fast": true}')

    def test_fail_fast_unknown_method(self):
        response = frontik_test_app.get_page('fail_fast?fail_fast=true', method=requests.head)
        self.assertEqual(response.status_code, 401)

    def test_fail_fast_without_done(self):
        response = frontik_test_app.get_page('fail_fast/fail_fast_without_done')
        self.assertEqual(response.status_code, 401)

    def test_fail_fast_default(self):
        response = frontik_test_app.get_page('fail_fast?fail_fast_default=true&code=400', method=requests.post)
        self.assertEqual(response.status_code, 400)

        response = frontik_test_app.get_page('fail_fast?fail_fast_default=true&code=500', method=requests.post)
        self.assertEqual(response.status_code, 502)

    def test_future(self):
        json = frontik_test_app.get_page_json('fail_fast/future')

        future_result = json['future']
        self.assertEqual(future_result, 'future_result')

    def test_future_fail(self):
        response = frontik_test_app.get_page('fail_fast/future?fail_future=true')
        self.assertEqual(response.status_code, 500)

    def test_exception_in_fail_fast(self):
        response = frontik_test_app.get_page('fail_fast?fail_fast=true&exception_in_fail_fast=true')
        self.assertEqual(response.status_code, 500)

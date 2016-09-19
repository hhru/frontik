# coding=utf-8

import requests
import unittest

from .instances import frontik_non_debug, frontik_test_app


class TestHandler(unittest.TestCase):
    def test_active_limit(self):
        text = frontik_non_debug.get_page_text('recursion?n=6')
        self.assertEqual(text, '200 200 200 200 200 503')

    def test_check_finished(self):
        text = frontik_test_app.get_page_text('handler/check_finished')
        self.assertEqual(text, 'Callback not called')

        # Check that callback has not been called at later IOLoop iteration

        text = frontik_test_app.get_page_text('handler/check_finished')
        self.assertEqual(text, 'Callback not called')

    def test_head(self):
        response = frontik_test_app.get_page('handler/head', method=requests.head)
        self.assertEqual(response.headers['X-Foo'], 'Bar')
        self.assertEqual(response.content, b'')

    def test_head_url(self):
        response = frontik_test_app.get_page('handler/head_url')
        self.assertEqual(response.content, b'OK')

    def test_no_method(self):
        response = frontik_test_app.get_page('handler/head', method=requests.post)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.headers['Allow'], 'get')

    def test_set_status(self):
        response = frontik_test_app.get_page('http_error?code=401&throw=false')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content, b'success')

    def test_set_extended_status(self):
        response = frontik_test_app.get_page('http_error?code=429&throw=false')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.content, b'success')

    def test_delete_post_arguments(self):
        response = frontik_test_app.get_page('handler/delete', method=requests.delete)
        self.assertEqual(response.status_code, 400)

    def test_finish_group_done_hook(self):
        response = frontik_test_app.get_page('handler/finish_group_done_hook')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'content')
        self.assertEqual(response.headers['X-Custom-Header'], 'value')

        response = frontik_test_app.get_page('handler/finish_group_done_hook?exception_in_handler=true')
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'500: Internal Server Error', response.content)
        self.assertNotIn('X-Custom-Header', response.headers)

        response = frontik_test_app.get_page('handler/finish_group_done_hook?exception_in_hook=true')
        self.assertIn(b'400: Bad Request', response.content)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('X-Custom-Header', response.headers)

    def test_before_finish_hook(self):
        response = frontik_test_app.get_page('handler/before_finish_hook')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'content')
        self.assertEqual(response.headers['X-Custom-Header'], 'value')

        response = frontik_test_app.get_page('handler/before_finish_hook?exception_in_handler=true')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers['X-Custom-Header'], 'value')

        response = frontik_test_app.get_page('handler/before_finish_hook?exception_in_hook=true')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'400: Bad Request', response.content)
        self.assertNotIn('X-Custom-Header', response.headers)

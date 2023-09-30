import unittest

import requests

from frontik import media_types
from tests.instances import frontik_no_debug_app, frontik_test_app


class TestHandler(unittest.TestCase):
    def test_active_limit(self):
        text = frontik_no_debug_app.get_page_text('recursion?n=6')
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

    async def test_head_url(self):
        response = frontik_test_app.get_page('handler/head_url')
        self.assertEqual(b'OK', response.content)

    def test_no_method(self):
        response = frontik_test_app.get_page('handler/head', method=requests.post)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.headers['Allow'], 'get')

    def test_delete_post_arguments(self):
        response = frontik_test_app.get_page('handler/delete', method=requests.delete)
        self.assertEqual(response.status_code, 400)

    def test_204(self):
        response = frontik_test_app.get_page('finish_204')
        self.assertEqual(response.status_code, 204)

    def test_get_json_body(self):
        for method in (requests.post, requests.put):
            # check if it works just fine
            response = frontik_test_app.get_page(
                'handler/json',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                json={'foo': 'bar'},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b'bar')

    # check if it raises HTTPError(400) on JSONDecodeException
    def test_json_decode_exception(self):
        for method in (requests.post, requests.put):
            response = frontik_test_app.get_page(
                'handler/json',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                data=b'',
            )
            self.assertEqual(response.status_code, 400)

            response = frontik_test_app.get_page(
                'handler/json_optional_args',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                data=b'',
            )
            self.assertEqual(response.status_code, 400)

    # check if it raises HTTPError(400) only when there's no default param
    def test_get_json_body_optional_args(self):
        for method in (requests.post, requests.put):
            response = frontik_test_app.get_page(
                'handler/json',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                json={},
            )
            self.assertEqual(response.status_code, 400)

            response = frontik_test_app.get_page(
                'handler/json_optional_args',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                json={},
            )
            self.assertEqual(response.content, b'baz')


class TestRedirectHandler(unittest.TestCase):
    def test_permanent_redirect(self):
        response = frontik_test_app.get_page('redirect/permanent', allow_redirects=False)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers['Location'], '/finish?foo=bar')

    def test_temporary_redirect(self):
        response = frontik_test_app.get_page('redirect/temporary', allow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/finish?foo=bar')

    def test_permanent_redirect_with_argument(self):
        response = frontik_test_app.get_page('redirect/permanent?foo2=bar2', allow_redirects=False)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers['Location'], '/finish?foo=bar&foo2=bar2')

    def test_temporary_redirect_with_argument(self):
        response = frontik_test_app.get_page('redirect/temporary?foo2=bar2', allow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/finish?foo=bar&foo2=bar2')

    def test_permanent_followed_redirect(self):
        response = frontik_test_app.get_page('redirect/permanent', allow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'success')

    def test_permanent_followed_redirect_with_argument(self):
        response = frontik_test_app.get_page('redirect/permanent?code=403', allow_redirects=True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'success')

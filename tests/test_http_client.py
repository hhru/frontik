import unittest

from .instances import frontik_test_app


class TestHttpClient(unittest.TestCase):
    def test_post_url_simple(self):
        text = frontik_test_app.get_page_text('http_client/post_simple')
        self.assertEqual(text, 'post_url success')

    def test_post_url_mfd(self):
        response = frontik_test_app.get_page('http_client/post_url')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"errors_count": 0}')

    def test_delete_query_arguments(self):
        json = frontik_test_app.get_page_json('handler/delete')
        self.assertEqual(json['delete'], 'true')

    def test_fib0(self):
        text = frontik_test_app.get_page_text('http_client/fibonacci?n=0')
        self.assertEqual(text, '1')

    def test_fib2(self):
        text = frontik_test_app.get_page_text('http_client/fibonacci?n=2')
        self.assertEqual(text, '2')

    def test_fib6(self):
        text = frontik_test_app.get_page_text('http_client/fibonacci?n=6')
        self.assertEqual(text, '13')

    def test_timeout(self):
        json = frontik_test_app.get_page_json('http_client/long_page_request')
        self.assertEqual(json, {'error_received': True})

    def test_parse_error(self):
        """ If json or xml parsing error occurs, we must send None into callback. """
        text = frontik_test_app.get_page_text('http_client/parse_error')
        self.assertEqual(text, 'Parse error occured')

    def test_parse_response(self):
        json = frontik_test_app.get_page_json('http_client/parse_response')
        self.assertEqual(
            json, {'post': True, 'delete': 'deleted', 'error': {'reason': 'HTTP 400: Bad Request', 'code': 400}}
        )

    def test_custom_headers(self):
        json = frontik_test_app.get_page_json('http_client/custom_headers')
        self.assertEqual(json['X-Foo'], 'Bar')

    def test_http_client_method_future(self):
        json = frontik_test_app.get_page_json('http_client/future')
        self.assertEqual(json, {'additional_callback_called': True})

    def test_http_raise_error(self):
        text = frontik_test_app.get_page_text('http_client/raise_error')
        self.assertEqual(text, 'UnicodeEncodeError')

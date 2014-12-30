# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestHttpError(unittest.TestCase):
    def test_raise_200(self):
        response = frontik_test_app.get_page('http_error')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, 'success')

    def test_raise_401(self):
        response = frontik_test_app.get_page('http_error?code=401')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.raw.reason, 'Unauthorized')
        self.assertEqual(response.headers['X-Foo'], 'Bar')
        self.assertEqual(response.headers['Content-Type'], 'text/html; charset=UTF-8')
        self.assertEqual(
            response.content,
            u'<html><title>401: Unauthorized</title><body>401: Unauthorized</body></html>'
        )

    def test_raise_extended_code(self):
        response = frontik_test_app.get_page('http_error?code=429')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['X-Foo'], 'Bar')
        self.assertEqual(response.headers['Content-Type'], 'text/html; charset=UTF-8')
        self.assertEqual(
            response.content,
            u'<html><title>429: Too Many Requests</title><body>429: Too Many Requests</body></html>'
        )

    def test_raise_with_unknown_code(self):
        response = frontik_test_app.get_page('http_error?code=599')
        self.assertEqual(response.status_code, 503)

    def test_finish_with_unknown_code(self):
        response = frontik_test_app.get_page('http_error?code=599&throw=false')
        self.assertEqual(response.status_code, 503)

    def test_http_error_xml(self):
        response = frontik_test_app.get_page('xsl/simple?raise=true')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, '<html><body>\n<h1>ok</h1>\n<h1>not ok</h1>\n</body></html>\n')

    def test_http_error_text(self):
        response = frontik_test_app.get_page('test_exception_text')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, 'This is just a plain text')

    def test_http_error_json(self):
        response = frontik_test_app.get_page('test_exception_json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, '{"reason": "bad argument"}')

    def test_http_error_in_prepare(self):
        response = frontik_test_app.get_page('http_error_in_prepare')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers['X-Foo'], 'Bar')

    def test_write_error(self):
        response = frontik_test_app.get_page('write_error')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content, '{"write_error": true}')

    def test_write_error_exception(self):
        response = frontik_test_app.get_page('write_error?fail_write_error=true')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content, '')

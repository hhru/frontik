import unittest

import requests

from frontik import media_types
from tests.instances import frontik_test_app


class TestHttpError(unittest.TestCase):
    _CODES_MAPPING = {200: 200, 401: 401, 599: 503}

    def test_raise_200(self):
        response = frontik_test_app.get_page('http_error?code=200')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'<html><title>200: OK</title><body>200: OK</body></html>')

    def test_raise_401(self):
        response = frontik_test_app.get_page('http_error?code=401')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.raw.reason, 'Unauthorized')
        self.assertEqual(response.headers['content-type'], media_types.TEXT_HTML)
        self.assertEqual(
            response.content,
            b'<html><title>401: Unauthorized</title><body>401: Unauthorized</body></html>',
        )

    def test_raise_unknown_code(self):
        response = frontik_test_app.get_page('http_error?code=599')
        self.assertEqual(response.status_code, 503)

    def test_405(self):
        response = frontik_test_app.get_page('http_error', method=requests.put)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.headers['allow'], 'get')

    def test_finish_200(self):
        for code, actual_code in self._CODES_MAPPING.items():
            response = frontik_test_app.get_page(f'finish?code={code}&throw=false')
            self.assertEqual(response.status_code, actual_code)
            self.assertEqual(response.headers['x-foo'], 'Bar')
            self.assertEqual(response.content, b'success')

    def test_finish_exception(self):
        for code, actual_code in self._CODES_MAPPING.items():
            response = frontik_test_app.get_page(f'finish?code={code}&throw=true')
            self.assertEqual(response.status_code, actual_code)
            self.assertEqual(response.headers['x-foo'], 'Bar')
            self.assertEqual(response.content, b'success')

    def test_http_error_xml(self):
        response = frontik_test_app.get_page('xsl/simple?raise=true')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'<html><body>\n<h1>ok</h1>\n<h1>not ok</h1>\n</body></html>\n')

    def test_http_error_text(self):
        response = frontik_test_app.get_page('test_exception_text')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'This is just a plain text')

    def test_http_error_json(self):
        response = frontik_test_app.get_page('test_exception_json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'{"reason": "bad argument"}')

    def test_write_error(self) -> None:
        response = frontik_test_app.get_page('write_error')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content, b'{"write_error": true}')

    def test_write_error_exception(self) -> None:
        response = frontik_test_app.get_page('write_error?fail_write_error=true')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content, b'')

    def test_write_error_405(self):
        response = frontik_test_app.get_page('write_error', method=requests.put)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.headers['allow'], 'get')
        self.assertEqual(response.content, b'')

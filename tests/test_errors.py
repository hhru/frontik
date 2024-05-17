import requests

from frontik import media_types
from tests.instances import frontik_test_app


class TestHttpError:
    _CODES_MAPPING = {200: 200, 401: 401, 599: 503}

    def test_raise_200(self):
        response = frontik_test_app.get_page('http_error?code=200')
        assert response.status_code == 200
        assert response.headers.get('content-type') == media_types.TEXT_HTML
        assert response.content == b'<html><title>200: OK</title><body>200: OK</body></html>'

    def test_raise_401(self):
        response = frontik_test_app.get_page('http_error?code=401')
        assert response.status_code == 401
        assert response.raw.reason == 'Unauthorized'
        assert response.headers['content-type'] == media_types.TEXT_HTML
        assert response.content == b'<html><title>401: Unauthorized</title><body>401: Unauthorized</body></html>'

    def test_405(self):
        response = frontik_test_app.get_page('http_error', method=requests.put)
        assert response.status_code == 405
        assert response.headers['allow'] == 'GET'

    def test_finish_200(self):
        for code, actual_code in self._CODES_MAPPING.items():
            response = frontik_test_app.get_page(f'finish?code={code}')
            assert response.status_code == actual_code
            assert response.headers['x-foo'] == 'Bar'
            assert response.content == b'success'

    def test_http_error_xml(self):
        response = frontik_test_app.get_page('xsl/simple?raise=true')
        assert response.status_code == 400
        assert response.content == b'<html><body>\n<h1>ok</h1>\n<h1>not ok</h1>\n</body></html>\n'

    def test_http_error_text(self):
        response = frontik_test_app.get_page('test_exception_text')
        assert response.status_code == 403
        assert response.content == b'This is just a plain text'

    def test_http_error_json(self):
        response = frontik_test_app.get_page('test_exception_json')
        assert response.status_code == 400
        assert response.content == b'{"reason":"bad argument"}'

    def test_write_error(self) -> None:
        response = frontik_test_app.get_page('write_error')
        assert response.status_code == 500
        assert response.content == b'{"write_error":true}'

    def test_write_error_exception(self) -> None:
        response = frontik_test_app.get_page('write_error?fail_write_error=true')
        assert response.status_code == 500
        assert response.content == b'Internal Server Error'

    def test_write_error_405(self):
        response = frontik_test_app.get_page('write_error', method=requests.put)
        assert response.status_code == 405
        assert response.headers['allow'] == 'GET'
        assert response.content == b''

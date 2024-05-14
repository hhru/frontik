import requests

from frontik import media_types
from tests.instances import frontik_no_debug_app, frontik_test_app


class TestHandler:
    def test_active_limit(self):
        text = frontik_no_debug_app.get_page_text('recursion?n=6')
        assert text == '200 200 200 200 200 503'

    def test_head(self):
        response = frontik_test_app.get_page('handler/head', method=requests.head)
        assert response.headers['X-Foo'] == 'Bar'
        assert response.content == b''

    async def test_head_url(self):
        response = frontik_test_app.get_page('handler/head_url')
        assert b'OK' == response.content

    def test_no_method(self):
        response = frontik_test_app.get_page('handler/head', method=requests.post)
        assert response.status_code == 405
        assert response.headers['Allow'] == 'HEAD'

    def test_delete_post_arguments(self):
        response = frontik_test_app.get_page('handler/delete', method=requests.delete)
        assert response.status_code == 400

    def test_204(self):
        response = frontik_test_app.get_page('finish_204')
        assert response.status_code == 204

    def test_get_json_body(self):
        for method in (requests.post, requests.put):
            # check if it works just fine
            response = frontik_test_app.get_page(
                'handler/json',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                json={'foo': 'bar'},
            )
            assert response.status_code == 200
            assert response.content == b'bar'

    # check if it raises HTTPException(400) on JSONDecodeException
    def test_json_decode_exception(self):
        for method in (requests.post, requests.put):
            response = frontik_test_app.get_page(
                'handler/json',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                data=b'',
            )
            assert response.status_code == 400

            response = frontik_test_app.get_page(
                'handler/json_optional_args',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                data=b'',
            )
            assert response.status_code == 400

    # check if it raises HTTPException(400) only when there's no default param
    def test_get_json_body_optional_args(self):
        for method in (requests.post, requests.put):
            response = frontik_test_app.get_page(
                'handler/json',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                json={},
            )
            assert response.status_code == 400

            response = frontik_test_app.get_page(
                'handler/json_optional_args',
                method=method,
                headers={'Content-Type': media_types.APPLICATION_JSON},
                json={},
            )
            assert response.content == b'baz'


class TestRedirectHandler:
    def test_permanent_redirect(self):
        response = frontik_test_app.get_page('redirect/permanent', allow_redirects=False)
        assert response.status_code == 301
        assert response.headers['Location'] == '/finish?foo=bar'

    def test_temporary_redirect(self):
        response = frontik_test_app.get_page('redirect/temporary', allow_redirects=False)
        assert response.status_code == 302
        assert response.headers['Location'] == '/finish?foo=bar'

    def test_permanent_redirect_with_argument(self):
        response = frontik_test_app.get_page('redirect/permanent?foo2=bar2', allow_redirects=False)
        assert response.status_code == 301
        assert response.headers['Location'] == '/finish?foo=bar&foo2=bar2'

    def test_temporary_redirect_with_argument(self):
        response = frontik_test_app.get_page('redirect/temporary?foo2=bar2', allow_redirects=False)
        assert response.status_code == 302
        assert response.headers['Location'] == '/finish?foo=bar&foo2=bar2'

    def test_permanent_followed_redirect(self):
        response = frontik_test_app.get_page('redirect/permanent', allow_redirects=True)
        assert response.status_code == 200
        assert response.content == b'success'

    def test_permanent_followed_redirect_with_argument(self):
        response = frontik_test_app.get_page('redirect/permanent?code=403', allow_redirects=True)
        assert response.status_code == 403
        assert response.content == b'success'

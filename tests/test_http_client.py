from tests.instances import frontik_test_app


class TestHttpClient:
    def test_post_url_simple(self):
        text = frontik_test_app.get_page_text('http_client/post_simple')
        assert text == 'post_url success'

    def test_post_url_mfd(self):
        response = frontik_test_app.get_page('http_client/post_url')
        assert response.status_code == 200
        assert response.content == b'{"errors_count":0}'

    def test_delete_query_arguments(self):
        json = frontik_test_app.get_page_json('handler/delete')
        assert json['delete'] == 'true'

    def test_fib0(self):
        text = frontik_test_app.get_page_text('http_client/fibonacci?n=0')
        assert text == '1'

    def test_fib2(self):
        text = frontik_test_app.get_page_text('http_client/fibonacci?n=2')
        assert text == '2'

    def test_fib6(self):
        text = frontik_test_app.get_page_text('http_client/fibonacci?n=6')
        assert text == '13'

    def test_timeout(self):
        json = frontik_test_app.get_page_json('http_client/long_page_request')
        assert json == {'error_received': True}

    def test_parse_error(self):
        """If json or xml parsing error occurs, we must send None into callback."""
        text = frontik_test_app.get_page_text('http_client/parse_error')
        assert text == 'Parse error occured'

    def test_parse_response(self):
        json = frontik_test_app.get_page_json('http_client/parse_response')
        assert json == {'post': True, 'delete': 'deleted', 'error': {'reason': 'Bad Request', 'code': 400}}

    def test_custom_headers(self):
        json = frontik_test_app.get_page_json('http_client/custom_headers')
        assert json['X-Foo'] == 'Bar'

    def test_http_client_method_future(self):
        json = frontik_test_app.get_page_json('http_client/future')
        assert json == {'additional_callback_called': True}

    def test_http_raise_error(self):
        response = frontik_test_app.get_page('http_client/raise_error')
        assert 200 == response.status_code

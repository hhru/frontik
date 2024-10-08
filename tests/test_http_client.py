import asyncio
import json

from frontik.handler import PageHandler, get_current_handler
from frontik.loggers import JSON_FORMATTER
from frontik.routing import plain_router
from frontik.testing import FrontikTestBase
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


@plain_router.get('/long_page', cls=PageHandler)
async def long_page() -> None:
    await asyncio.sleep(1)


@plain_router.get('/long_request', cls=PageHandler)
async def long_request(handler: PageHandler = get_current_handler()) -> None:
    await handler.get_url(handler.get_header('host'), '/long_page')


class TestRequestCancled(FrontikTestBase):
    async def test_request_canceled(self, caplog):
        caplog.handler.setFormatter(JSON_FORMATTER)
        response = await self.fetch('/long_request', request_timeout=0.1)
        await asyncio.sleep(2)

        assert response.status_code == 599

        for log_row in caplog.text.split('\n'):
            if log_row == '':
                continue
            log_obj = json.loads(log_row)
            assert log_obj.get('lvl') != 'ERROR', log_obj

import asyncio
from typing import Any

import pytest
import requests
import sentry_sdk
from fastapi import HTTPException

from frontik.app import FrontikApplication
from frontik.handler import PageHandler, get_current_handler
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase
from tests.instances import frontik_re_app, frontik_test_app


class Page(PageHandler):
    def initialize_sentry_logger(self):
        sentry_sdk.set_user({'id': '123456'})


@router.get('/sentry_error', cls=Page)
async def get_page(handler=get_current_handler()):
    ip = handler.get_query_argument('ip', None)
    extra = handler.get_query_argument('extra_key', None)
    a = 155
    if ip and extra:
        sentry_sdk.set_user({'real_ip': ip})
        sentry_sdk.set_extra('extra_key', extra)

    raise Exception('My_sentry_exception')


@router.post('/sentry_error', cls=Page)
async def post_page():
    raise HTTPException(500, 'my_HTTPError')


@router.put('/sentry_error', cls=Page)
async def put_page():
    sentry_sdk.set_extra('extra_key', 'extra_value')
    sentry_sdk.capture_message('sentry_message')


class TestSentryIntegration(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        frontik_test_app.start()
        options.sentry_dsn = f'http://secret@127.0.0.1:{frontik_test_app.port}/2'
        return FrontikApplication()

    async def test_sentry_exception(self):
        frontik_test_app.get_page('api/2/envelope/', method=requests.delete)

        await self.fetch('/sentry_error?ip=127.0.0.77&extra_key=extra_val')
        await asyncio.sleep(0.1)
        sentry_events = self._get_sentry_exceptions('My_sentry_exception')

        assert len(sentry_events) == 1
        event = sentry_events[0]
        assert len(event['breadcrumbs']['values']) == 0
        assert event.get('modules') is None
        assert event['request']['query_string'] == 'ip=127.0.0.77&extra_key=extra_val'
        assert event['user']['real_ip'] == '127.0.0.77'
        assert event['extra']['extra_key'] == 'extra_val'

        # second request for check that sentry scope was overwritten
        await self.fetch('sentry_error')
        await asyncio.sleep(0.1)
        sentry_events = self._get_sentry_exceptions('My_sentry_exception')

        assert len(sentry_events) == 2
        event = sentry_events[1]
        assert event['user'].get('real_ip') is None
        assert event.get('extra') is None

    async def test_sentry_message(self):
        frontik_test_app.get_page('api/2/envelope/', method=requests.delete)
        await self.fetch('sentry_error', method='PUT', headers={'MaHeaderKey': 'MaHeaderValue'})

        sentry_events = self._get_sentry_messages()
        sentry_events = list(filter(lambda e: e.get('message') == 'sentry_message', sentry_events))
        assert len(sentry_events) == 1

        event = sentry_events[0]
        assert len(event['breadcrumbs']['values']) == 0
        assert event.get('modules') is None
        assert event['request']['url'].endswith('/sentry_error') is True
        assert event['request']['method'] == 'PUT'
        assert event['request']['headers']['maheaderkey'] == 'MaHeaderValue'
        assert event['extra']['extra_key'] == 'extra_value'
        assert event['user']['id'] == '123456'

    async def test_sentry_http_error(self):
        frontik_test_app.get_page('api/2/envelope/', method=requests.delete)
        await self.fetch('sentry_error', method='POST')

        sentry_events = self._get_sentry_exceptions('my_HTTPError')
        assert len(sentry_events) == 0, 'HTTPException must not be sent to Sentry'

    def test_sentry_not_configured(self):
        assert 200 == frontik_re_app.get_page('sentry_not_configured').status_code

    @staticmethod
    def _get_sentry_messages() -> list[dict[str, Any]]:
        sentry_json = frontik_test_app.get_page_json('api/2/envelope/')
        return sentry_json['exceptions']

    @staticmethod
    def _get_sentry_exceptions(name: str) -> list[dict[str, Any]]:
        sentry_json = frontik_test_app.get_page_json('api/2/envelope/')
        return list(filter(lambda event: filter_sentry_event(event, name), sentry_json['exceptions']))


def filter_sentry_event(event: dict, name: str) -> bool:
    return event.get('exception', {}).get('values', [{}])[0].get('value', None) == name

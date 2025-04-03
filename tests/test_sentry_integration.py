import asyncio
import gzip
import json
from typing import Any, Optional

import pytest
import sentry_sdk
from fastapi import Request
from tornado.web import HTTPError

from frontik.app import FrontikApplication
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase

exceptions = []


@router.get('/sentry_error')
async def get_page(ip: Optional[str] = None, extra_key: Optional[str] = None) -> None:
    if ip and extra_key:
        sentry_sdk.set_user({'real_ip': ip})
        sentry_sdk.set_extra('extra_key', extra_key)

    raise Exception('My_sentry_exception')


@router.post('/sentry_error')
async def post_page():
    raise HTTPError(500, 'my_HTTPError')


@router.put('/sentry_error')
async def put_page():
    sentry_sdk.set_extra('extra_key', 'extra_value')
    sentry_sdk.capture_message('sentry_message')


@router.post('/api/2/envelope/')
async def post_to_sentry(request: Request) -> None:
    messages = gzip.decompress(await request.body()).decode('utf8')

    for message in messages.split('\n'):
        if message == '':
            continue
        sentry_event = json.loads(message)
        exceptions.append(sentry_event)


class TestSentryIntegration(FrontikTestBase):
    @classmethod
    def teardown_class(cls):
        options.sentry_dsn = None

    def teardown_method(self, method):
        exceptions.clear()

    @pytest.fixture(scope='class')
    def frontik_app(self, _bind_socket) -> FrontikApplication:  # type: ignore
        options.sentry_dsn = f'http://secret@127.0.0.1:{options.port}/2'
        sentry_sdk.set_user({'id': '123456'})
        return FrontikApplication(app_module_name=None)

    async def test_sentry_exception(self):
        await self.fetch('/sentry_error?ip=127.0.0.77&extra_key=extra_val')
        await asyncio.sleep(0.1)
        sentry_events = _get_sentry_exceptions('My_sentry_exception')

        assert len(sentry_events) == 1
        event = sentry_events[0]
        assert len(event['breadcrumbs']['values']) == 0
        assert event.get('modules') is not None
        assert event['request']['query_string'] == 'ip=127.0.0.77&extra_key=extra_val'
        assert event['user']['real_ip'] == '127.0.0.77'
        assert event['extra']['extra_key'] == 'extra_val'

        # second request for check that sentry scope was overwritten
        await self.fetch('/sentry_error')
        await asyncio.sleep(0.1)
        sentry_events = _get_sentry_exceptions('My_sentry_exception')

        assert len(sentry_events) == 2
        event = sentry_events[1]
        assert event.get('user', {}).get('real_ip') is None
        assert event.get('extra') is None

    async def test_sentry_message(self):
        await self.fetch('/sentry_error', method='PUT', headers={'MaHeaderKey': 'MaHeaderValue'})

        await asyncio.sleep(1)
        sentry_events = list(filter(lambda e: e.get('message') == 'sentry_message', exceptions))
        assert len(sentry_events) == 1

        event = sentry_events[0]
        assert len(event['breadcrumbs']['values']) == 0
        assert event.get('modules') is not None
        assert event['request']['url'].endswith('/sentry_error') is True
        assert event['request']['method'] == 'PUT'
        assert event['request']['headers']['maheaderkey'] == 'MaHeaderValue'
        assert event['extra']['extra_key'] == 'extra_value'
        assert event['user']['id'] == '123456'

    async def test_sentry_http_error(self):
        await self.fetch('/sentry_error', method='POST')

        sentry_events = _get_sentry_exceptions('my_HTTPError')
        assert len(sentry_events) == 0, 'HTTPException must not be sent to Sentry'


class TestWithoutSentryIntegration(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    def test_sentry_not_configured(self):
        assert not options.sentry_dsn


def _get_sentry_exceptions(name: str) -> list[dict[str, Any]]:
    return list(filter(lambda event: filter_sentry_event(event, name), exceptions))


def filter_sentry_event(event: dict, name: str) -> bool:
    for item in event.get('exception', {}).get('values', [{}]):
        if item.get('value', None) == name:
            return True

    return False

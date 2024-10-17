import asyncio
import gzip
import json
from typing import Any

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
async def get_page(ip: str = None, extra_key: str = None) -> None:
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
async def post_page(request: Request):
    messages = gzip.decompress(await request.body()).decode('utf8')

    for message in messages.split('\n'):
        if message == '':
            continue
        sentry_event = json.loads(message)
        exceptions.append(sentry_event)


@router.get('/api/2/envelope/')
async def get_page():
    return {'exceptions': exceptions}


@router.delete('/api/2/envelope/')
async def delete_page():
    exceptions.clear()


class TestSentryIntegration(FrontikTestBase):
    @classmethod
    def teardown_class(cla):
        options.sentry_dsn = None

    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        app = FrontikApplication()
        old_init = app.init

        async def _init():
            options.sentry_dsn = f'http://secret@127.0.0.1:{options.port}/2'
            await old_init()
            sentry_sdk.set_user({'id': '123456'})
        app.init = _init
        return app

    async def test_sentry_exception(self):
        await self.fetch('/api/2/envelope/', method='DELETE')

        await self.fetch('/sentry_error?ip=127.0.0.77&extra_key=extra_val')
        await asyncio.sleep(0.1)
        sentry_events = await self._get_sentry_exceptions('My_sentry_exception')

        assert len(sentry_events) == 1
        event = sentry_events[0]
        # assert event['transaction'] == 'frontik.handler.PageHandler.get'
        assert len(event['breadcrumbs']['values']) == 0
        assert event.get('modules') is not None
        assert event['request']['query_string'] == 'ip=127.0.0.77&extra_key=extra_val'
        assert event['user']['real_ip'] == '127.0.0.77'
        assert event['extra']['extra_key'] == 'extra_val'

        # second request for check that sentry scope was overwritten
        await self.fetch('/sentry_error')
        await asyncio.sleep(0.1)
        sentry_events = await self._get_sentry_exceptions('My_sentry_exception')

        assert len(sentry_events) == 2
        event = sentry_events[1]
        assert event.get('user', {}).get('real_ip') is None
        assert event.get('extra') is None

    async def test_sentry_message(self):
        await self.fetch('/api/2/envelope/', method='DELETE')
        await self.fetch('/sentry_error', method='PUT', headers={'MaHeaderKey': 'MaHeaderValue'})

        await asyncio.sleep(1)
        sentry_events = await self._get_sentry_messages()
        sentry_events = list(filter(lambda e: e.get('message') == 'sentry_message', sentry_events))
        assert len(sentry_events) == 1

        event = sentry_events[0]
        assert len(event['breadcrumbs']['values']) == 0
        assert event.get('modules') is not None
        assert event['request']['url'].endswith('/sentry_error') is True
        assert event['request']['method'] == 'PUT'
        # assert event['request']['headers']['Maheaderkey'] == 'MaHeaderValue'
        assert event['request']['headers']['maheaderkey'] == 'MaHeaderValue'
        assert event['extra']['extra_key'] == 'extra_value'
        assert event['user']['id'] == '123456'

    async def test_sentry_http_error(self):
        await self.fetch('/api/2/envelope/', method='DELETE')
        await self.fetch('/sentry_error', method='POST')

        sentry_events = await self._get_sentry_exceptions('my_HTTPError')
        assert len(sentry_events) == 0, 'HTTPException must not be sent to Sentry'

    async def _get_sentry_messages(self) -> list[dict[str, Any]]:
        sentry_raw = await self.fetch('/api/2/envelope/')
        return sentry_raw.data['exceptions']

    async def _get_sentry_exceptions(self, name: str) -> list[dict[str, Any]]:
        sentry_raw = await self.fetch('/api/2/envelope/')
        sentry_json = sentry_raw.data
        return list(filter(lambda event: filter_sentry_event(event, name), sentry_json['exceptions']))


class TestWithoutSentryIntegration(FrontikTestBase):
    def test_sentry_not_configured(self):
        assert not options.sentry_dsn


def filter_sentry_event(event: dict, name: str) -> bool:
    return event.get('exception', {}).get('values', [{}])[0].get('value', None) == name

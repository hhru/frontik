import asyncio
import math

import pytest
from fastapi import Request
from fastapi.responses import Response
from starlette.requests import ClientDisconnect

from frontik.app import FrontikApplication
from frontik.media_types import TEXT_PLAIN
from frontik.routing import router
from frontik.testing import FrontikTestBase

DATA = b'x' * 10_000_000

RESULT_HOLDER = {'streaming_request_client_disconnect': 'not_set'}


@router.post('/streaming_request')
async def get_page(request: Request) -> Response:
    chunks_count = 0
    async for chunk in request.stream():
        if chunk != b'':
            chunks_count += 1
    assert chunks_count == math.ceil(len(DATA) / 65536)

    return Response(headers={'Content-type': TEXT_PLAIN})


@router.post('/streaming_request_client_disconnect')
async def get_page_fail(request: Request) -> Response:
    with pytest.raises(ClientDisconnect):
        async for _ in request.stream():
            pass
    RESULT_HOLDER['streaming_request_client_disconnect'] = 'success'
    return Response(headers={'Content-type': TEXT_PLAIN})


class TestStreamingRequest(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    async def test_streaming_request(self) -> None:
        response = await self.fetch(
            method='POST',
            path='/streaming_request',
            data={'field': 'value'},
            files={'file_file': [{'filename': 'file_name', 'body': DATA}]},
        )
        assert response.status_code == 200

    async def test_streaming_request_canceled(self) -> None:
        await self.fetch(
            method='POST',
            path='/streaming_request_client_disconnect',
            data={'field': 'value'},
            files={'file_file': [{'filename': 'file_name', 'body': DATA}]},
            request_timeout=0.01,
        )
        await asyncio.sleep(1)
        assert RESULT_HOLDER['streaming_request_client_disconnect'] == 'success'

import math

import pytest
from fastapi import Request
from fastapi.responses import Response

from frontik.app import FrontikApplication
from frontik.media_types import TEXT_PLAIN
from frontik.routing import router
from frontik.testing import FrontikTestBase

DATA = b'x' * 1_000_000


@router.post('/streaming_request')
async def get_page(request: Request) -> Response:
    chunks_count = 0
    async for chunk in request.stream():
        if chunk != b'':
            chunks_count += 1

    assert chunks_count == math.ceil(len(DATA) / 65536)

    return Response(headers={'Content-type': TEXT_PLAIN})


class TestStreamingRequest(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    async def test_streaming_request(self):
        await self.fetch(
            method='POST',
            path='/streaming_request',
            data={'field': 'value'},
            files={'file_file': [{'filename': 'file_name', 'body': DATA}]},
        )

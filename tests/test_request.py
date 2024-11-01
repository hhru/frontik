import pytest
from fastapi import Request
from fastapi.responses import ORJSONResponse, Response

from frontik.app import FrontikApplication
from frontik.routing import router
from frontik.testing import FrontikTestBase

DATA = {'body_arg': 'value'}


@router.post('/echo')
async def echo_handler(request: Request) -> Response:
    return ORJSONResponse(content=dict(await request.form()))


class TestStreamingRequest(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication()

    async def test_post_request_with_body(self):
        response = await self.fetch(
            method='POST',
            path='/echo',
            data=DATA,
        )
        assert response.data == DATA

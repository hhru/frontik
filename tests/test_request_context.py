from frontik import request_context
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/request_context')
async def get_page():
    return request_context.get_handler_name()


class TestRequestContext(FrontikTestBase):
    async def test_request_context(self):
        response = await self.fetch('/request_context')
        controller = 'tests.test_request_context.get_page'
        assert response.data == controller

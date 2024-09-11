from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/example', cls=PageHandler)
async def example_page(self: PageHandler = get_current_handler()) -> None:
    result = await self.get_url('http://example.com', '/')
    self.json.put({'example': result.status_code})

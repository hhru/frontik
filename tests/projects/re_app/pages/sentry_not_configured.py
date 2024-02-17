import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        assert not hasattr(self, 'get_sentry_logger')

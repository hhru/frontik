import frontik.handler


class Page(frontik.handler.AwaitablePageHandler):
    async def get_page(self):
        assert not hasattr(self, 'get_sentry_logger')

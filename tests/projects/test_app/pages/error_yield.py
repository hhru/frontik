import frontik.handler


async def some_async_function(handler: frontik.handler.PageHandler) -> float:
    await handler.post_url(handler.request.host, handler.request.path)
    return 1 / 0


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.finish_group.add_future(some_async_function(self))  # type: ignore

    async def post_page(self):
        self.text = 'result'

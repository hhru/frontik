import frontik.handler


class Page(frontik.handler.AwaitablePageHandler):
    async def get_page(self):
        self.require_debug_access('user', 'god')
        self.json.put({'authenticated': True})

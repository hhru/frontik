import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.require_debug_access('user', 'god')
        self.json.put({'authenticated': True})

import frontik.handler
from frontik.options import options


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        resp = await self.get_url(f'127.0.0.1:{options.port}', '/handler_with_large_json_body', fail_fast=True)
        self.json.put(resp.data)

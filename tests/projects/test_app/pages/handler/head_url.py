import http.client

import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        head_result = await self.head_url(self.request.host, '/handler/head', name='head')

        if head_result.data == b'' and head_result.status_code == http.client.OK:
            self.text = 'OK'

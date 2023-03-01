import asyncio

from frontik import media_types
from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        n = int(self.get_argument('n'))

        self.add_header('Content-Type', media_types.TEXT_PLAIN)

        if n < 2:
            self.text = '1'
            return

        self.acc = 0

        r1, r2 = await asyncio.gather(
            self.get_url(self.request.host, self.request.path, data={'n': str(n - 1)}),
            self.get_url(self.request.host, self.request.path, data={'n': str(n - 2)})
        )
        self.acc += int(r1.data)
        self.acc += int(r2.data)
        self.text = str(self.acc)

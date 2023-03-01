from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.util import gather_list


class Page(PageHandler):
    async def get_page(self):
        port = int(self.get_argument('port'))

        @self.check_finished
        def cb(*args, **kw):
            raise HTTPError(400)

        results = await gather_list(
            self.get_url(f'http://localhost:{port}', '/page/simple/'),
            self.get_url(f'http://localhost:{port}', '/page/simple/'),
            self.get_url(f'http://localhost:{port}', '/page/simple/')
        )
        for res in results:
            cb(res)

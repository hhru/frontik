from tornado.web import HTTPError

from frontik.handler import AwaitablePageHandler


class Page(AwaitablePageHandler):
    async def put_page(self):
        raise HTTPError(503, 'broken, retry')

from tornado.web import HTTPError

from frontik.handler import AwaitablePageHandler


class Page(AwaitablePageHandler):
    async def post_page(self):
        raise HTTPError(500, 'something went wrong, no retry')

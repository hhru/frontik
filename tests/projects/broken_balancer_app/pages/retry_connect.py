from tornado.web import HTTPError

from frontik.handler import PageHandler, router


class Page(PageHandler):
    @router.post()
    async def post_page(self):
        raise HTTPError(503, 'broken, retry')

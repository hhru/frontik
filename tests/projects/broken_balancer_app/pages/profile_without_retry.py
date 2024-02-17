from tornado.web import HTTPError

from frontik import handler
from frontik.handler import router


class Page(handler.PageHandler):
    @router.put()
    async def put_page(self):
        raise HTTPError(503, 'broken')

from tornado.web import HTTPError

from frontik import handler


class Page(handler.PageHandler):
    def put_page(self):
        raise HTTPError(503, 'broken')

from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        code = int(self.get_argument('code', '200'))
        raise HTTPError(code)

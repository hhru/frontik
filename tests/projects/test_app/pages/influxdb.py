from tornado import gen

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        yield self.post_url(self.request.host, '/')
        yield gen.sleep(0.1)

    def post_page(self):
        pass

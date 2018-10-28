# coding=utf-8

from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        port = int(self.get_argument('port'))

        @self.check_finished
        def cb(*args, **kw):
            raise HTTPError(400)

        self.get_url('http://localhost:{}'.format(port), '/page/simple/', callback=cb)
        self.get_url('http://localhost:{}'.format(port), '/page/simple/', callback=cb)
        self.get_url('http://localhost:{}'.format(port), '/page/simple/', callback=cb)

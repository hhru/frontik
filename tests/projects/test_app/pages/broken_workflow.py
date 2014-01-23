import tornado.web

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        port = int(self.get_argument('port'))

        @self.check_finished
        def cb(*args, **kw):
            raise tornado.web.HTTPError(400)

        self.get_url('http://localhost:{0}/page/simple/'.format(port), callback=cb)
        self.get_url('http://localhost:{0}/page/simple/'.format(port), callback=cb)
        self.get_url('http://localhost:{0}/page/simple/'.format(port), callback=cb)

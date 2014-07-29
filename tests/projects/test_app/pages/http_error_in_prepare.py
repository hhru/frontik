import frontik.handler


class Page(frontik.handler.PageHandler):
    def prepare(self):
        raise frontik.handler.HTTPError(400, headers={'X-Foo': 'Bar'})

    def get_page(self):
        pass

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        raise frontik.handler.HTTPError(400, json={'reason': 'bad argument'})

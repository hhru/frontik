from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        self.write('data')
        self.set_status(204)

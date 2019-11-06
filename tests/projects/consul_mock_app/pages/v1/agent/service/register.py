from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        self.set_status(200)

    def put_page(self):
        self.set_status(200)

    def post_page(self):
        self.set_status(200)

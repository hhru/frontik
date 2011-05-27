import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.text = "success"
        raise frontik.handler.FinishException
        self.text = "fail"

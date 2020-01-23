from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        self.set_status(200)
        self.application.deregistration_call_counter['get_page'] += 1

    def put_page(self):
        self.set_status(200)
        self.application.deregistration_call_counter['put_page'] += 1

    def post_page(self):
        self.set_status(200)
        self.application.deregistration_call_counter['post_page'] += 1

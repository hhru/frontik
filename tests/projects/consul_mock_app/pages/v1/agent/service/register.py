from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.set_status(200)
        self.application.registration_call_counter['get_page'] += 1

    async def put_page(self):
        self.set_status(200)
        self.application.registration_call_counter['put_page'] += 1

    async def post_page(self):
        self.set_status(200)
        self.application.registration_call_counter['post_page'] += 1

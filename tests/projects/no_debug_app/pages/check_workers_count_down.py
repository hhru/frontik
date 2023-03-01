import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.text = str(self.application.init_workers_count_down.value)

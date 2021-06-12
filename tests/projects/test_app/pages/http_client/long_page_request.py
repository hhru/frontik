import time

import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.post_url(
            self.request.host, self.request.path,
            callback=self.request_callback, request_timeout=0.5
        )

    def request_callback(self, xml, response):
        self.json.put({'error_received': bool(response.error)})

    async def post_page(self):
        self.add_timeout(
            time.time() + 2, self.finish_group.add(self.check_finished(self.timeout_callback))
        )

    def timeout_callback(self):
        self.json.put({'timeout_callback': True})

import json

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.set_status(200)
        self.text = json.dumps(self.application.registration_call_counter)

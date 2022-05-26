import json

from frontik.handler import AwaitablePageHandler


class Page(AwaitablePageHandler):
    async def get_page(self):
        self.set_status(200)
        self.text = json.dumps(self.application.registration_call_counter)

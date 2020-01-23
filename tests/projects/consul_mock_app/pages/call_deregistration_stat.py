import json

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        self.set_status(200)
        self.text = json.dumps(self.application.deregistration_call_counter)

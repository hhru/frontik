import gzip
import json

import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    exceptions = []

    @router.post()
    async def post_page(self):
        message = gzip.decompress(self.request.body).decode('utf8')
        sentry_event = json.loads(message.split('\n')[-1])
        Page.exceptions.append(sentry_event)

    @router.get()
    async def get_page(self):
        self.json.put({'exceptions': Page.exceptions})

    @router.delete()
    async def delete_page(self):
        Page.exceptions = []

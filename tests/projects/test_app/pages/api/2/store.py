import gzip
import json

import frontik.handler


class Page(frontik.handler.PageHandler):
    exceptions = []

    async def post_page(self):
        message = gzip.decompress(self.request.body).decode('utf8')
        sentry_event = json.loads(message.split('\n')[-1])
        Page.exceptions.append(sentry_event)

    async def get_page(self):
        self.json.put({
            'exceptions': Page.exceptions
        })

    async def delete_page(self):
        Page.exceptions = []

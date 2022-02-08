import frontik.handler
from tornado.gen import coroutine

class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.log.debug("QQQ")
        request = yield self.post_url(
            self.request.host, 'Impossibleurl',
            fail_fast=True,
        )

        self.json.put({
            'text': 'Hello, world!'
        })

    def get_page_fail_fast(self, result):
        response = result.response
        code = response.code if response.code in (400, 403) else 502
        self.set_status(code)
        self.finish()

import time

import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.post()
    async def post_page(self):
        self.add_timeout(time.time() + 2, self.finish_group.add(self.check_finished(self.timeout_callback)))

    def timeout_callback(self):
        self.text = 'result'

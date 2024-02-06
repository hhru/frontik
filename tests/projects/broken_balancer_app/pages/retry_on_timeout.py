import time

from frontik import handler, media_types
from frontik.handler import router


class Page(handler.PageHandler):
    @router.delete()
    async def delete_page(self):
        self.add_timeout(time.time() + 2, self.finish_group.add(self.check_finished(self.timeout_callback)))

    def timeout_callback(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'

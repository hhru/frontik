import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    result = 'Callback not called'

    @router.get()
    async def get_page(self):
        # Callback must never be called
        def callback():
            Page.result = 'Callback called'

        self.add_callback(self.check_finished(callback))
        self.finish(Page.result)

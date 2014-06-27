# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    result = 'Callback not called'

    def get_page(self):
        # Callback must never be called
        def callback():
            Page.result = 'Callback called'

        self.add_callback(self.check_finished(callback))
        self.finish(Page.result)

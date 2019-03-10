import asyncio

from frontik.handler import PageHandler


class Page(PageHandler):
    counter_static = 0

    def prepare(self):
        super().prepare()

        self.counter = 0
        self.add_postprocessor(self._pp)

    @classmethod
    async def _pp(cls, handler):
        if handler.request.method != 'POST':
            handler.counter += 1
            cls.counter_static = handler.counter

            # create race condition between postprocessors
            if handler.counter == 1:
                await asyncio.sleep(0.1)
                handler.json.put({
                    'postprocessor_completed': True
                })

    def get_page(self):
        def _cb(_, __):
            # test that postprocessors are scheduled only once
            self.finish_with_postprocessors()

        self.post_url(self.request.host, self.request.uri, callback=_cb)

    def post_page(self):
        self.json.put({
            'counter': self.counter_static
        })

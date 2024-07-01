import asyncio

from frontik.handler import FinishWithPostprocessors, PageHandler, get_current_handler
from frontik.routing import router


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
                handler.json.put({'postprocessor_completed': True})


@router.get('/write_after_finish', cls=Page)
async def get_page(handler=get_current_handler()):
    await handler.post_url(handler.get_header('host'), handler.path)
    # test that postprocessors are scheduled only once
    raise FinishWithPostprocessors()


@router.post('/write_after_finish', cls=Page)
async def post_page(handler=get_current_handler()):
    handler.json.put({'counter': handler.counter_static})

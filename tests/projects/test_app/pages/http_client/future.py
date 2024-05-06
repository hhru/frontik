import asyncio

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/http_client/future', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()):
    state = {
        'second_callback_must_be_async': True,
    }

    def second_additional_callback(future):
        state['second_callback_must_be_async'] = False

    def additional_callback(future):
        assert future is request_future

        handler.json.put({'additional_callback_called': True})

        request_future.add_done_callback(handler.finish_group.add(second_additional_callback))
        assert state['second_callback_must_be_async']

    async def make_request():
        await handler.post_url(handler.get_header('host'), handler.path)

    request_future = asyncio.create_task(make_request())
    request_future.add_done_callback(handler.finish_group.add(additional_callback))


@router.post('/http_client/future', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.json.put({'yay': 'yay'})

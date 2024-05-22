import asyncio

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/http_client/future', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()):
    state = {
        'second_callback_must_be_async': True,
    }

    async def second_additional_callback():
        state['second_callback_must_be_async'] = False

    async def additional_callback():
        handler.json.put({'additional_callback_called': True})

        second_task = asyncio.create_task(second_additional_callback())
        request_future.add_done_callback(handler.finish_group.add_future(second_task))
        assert state['second_callback_must_be_async']

    async def make_request():
        await handler.post_url(handler.get_header('host'), handler.path)

    request_future = asyncio.create_task(make_request())
    additional_task = asyncio.create_task(additional_callback())
    request_future.add_done_callback(handler.finish_group.add_future(additional_task))


@router.post('/http_client/future', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.json.put({'yay': 'yay'})

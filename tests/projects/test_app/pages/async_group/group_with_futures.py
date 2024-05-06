from tornado.concurrent import Future

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from frontik.util import gather_dict


@router.get('/async_group/group_with_futures', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    future: Future = Future()

    if handler.get_query_argument('failed_future', 'false') == 'true':
        future.set_exception(Exception('failed future exception'))
    else:
        future.set_result({'1': 'yay'})

    another_future: Future = Future()
    another_future.set_result({'2': 'yay'})

    result = await gather_dict({'1': future, '2': another_future})
    handler.json.put({'final_callback_called': True})
    handler.json.put(result)

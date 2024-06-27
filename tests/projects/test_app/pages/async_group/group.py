from typing import Any

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from frontik.util import gather_dict


@router.get('/async_group/group', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    fail_callback = handler.get_query_argument('fail_callback', 'false') == 'true'
    fail_request = handler.get_query_argument('fail_request', 'false') == 'true'

    async def task() -> Any:
        request_result = await handler.post_url(handler.request.headers.get('host', ''), handler.path + '?data=2')
        if fail_callback:
            msg = "I'm dying!"
            raise Exception(msg)
        return request_result.data

    data = await gather_dict({
        '1': handler.post_url(handler.request.headers.get('host', ''), handler.path + '?data=1'),
        '2': task(),
        '3': handler.post_url(
            handler.request.headers.get('host', ''),
            handler.path,
            data={'data': '3' if not fail_request else None},
            parse_on_error=False,
        ),
    })
    handler.json.put(data)

    result = await gather_dict({
        '4': handler.post_url(handler.request.headers.get('host', ''), handler.path + '?data=4')
    })

    handler.json.put({'future_callback_result': result['4'].data['4']})
    handler.json.put({'final_callback_called': True})


@router.post('/async_group/group', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    data = handler.get_query_argument('data', None)
    if data is None:
        data = handler.get_body_argument('data')
    handler.json.put({data: 'yay'})

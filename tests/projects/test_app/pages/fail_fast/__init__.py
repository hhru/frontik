from fastapi import Depends

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, get_current_handler
from frontik.routing import router
from frontik.util import gather_dict


async def get_page_preprocessor(handler: PageHandler = get_current_handler()) -> None:
    handler.json.put({'preprocessor': True})


class Page(PageHandler):
    def get_page_fail_fast(self, failed_future):
        if self.get_argument('exception_in_fail_fast', 'false') == 'true':
            msg = 'Exception in fail_fast'
            raise Exception(msg)

        self.json.replace({'fail_fast': True})
        self.set_status(403)
        self.finish_with_postprocessors()


@router.get('/fail_fast', cls=Page, dependencies=[Depends(get_page_preprocessor)])
async def get_page(handler=get_current_handler()):
    fail_fast = handler.get_query_argument('fail_fast', 'false') == 'true'

    if handler.get_query_argument('return_none', 'false') == 'true':
        return

    results = await gather_dict({
        'get': handler.get_url(handler.get_header('host'), handler.path, data={'return_none': 'true'}, fail_fast=True),
        'post': handler.post_url(handler.get_header('host'), handler.path, data={'param': 'post'}),
        'put': handler.put_url(
            handler.get_header('host'),
            handler.path + '?code=401',
            fail_fast=fail_fast,
            parse_on_error=True,
        ),
        'delete': handler.delete_url(handler.get_header('host'), handler.path, data={'invalid_dict_value': 'true'}),
    })

    assert results['post'].status_code == 200
    assert results['put'].status_code == 401
    assert results['delete'].status_code == 500

    handler.json.put(results)


@router.post('/fail_fast', cls=Page)
async def post_page(handler=get_current_handler()):
    if handler.get_query_argument('fail_fast_default', 'false') == 'true':
        results = await gather_dict({
            'e': handler.put_url(
                handler.get_header('host'),
                '{}?code={}'.format(handler.path, handler.get_query_argument('code')),
                fail_fast=True,
            ),
        })

        handler.json.put(results)
    else:
        handler.json.put({'POST': handler.get_body_argument('param')})


@router.put('/fail_fast', cls=Page)
async def put_page(handler=get_current_handler()):
    # Testing parse_on_error=True
    handler.json.put({'error': 'forbidden'})
    raise HTTPErrorWithPostprocessors(int(handler.get_query_argument('code')))


@router.delete('/fail_fast', cls=Page)
async def delete_page(handler=get_current_handler()):
    # Testing invalid return values
    if handler.get_query_argument('invalid_dict_value', 'false') == 'true':
        raise Exception()

from asyncio import TimeoutError

from http_client.balancing import Upstream

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/no_retry_timeout', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['no_retry_timeout'] = Upstream('no_retry_timeout', {}, [get_server(handler, 'broken')])

    result = await handler.post_url('no_retry_timeout', handler.path, request_timeout=0.2)
    if result.failed and isinstance(result.exc, TimeoutError):
        handler.text = 'no retry timeout'
    else:
        handler.text = result.data

    check_all_requests_done(handler, 'no_retry_timeout')


@router.post('/no_retry_timeout', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

from http_client.balancing import Upstream

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/no_retry_error', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstreams = handler.application.service_discovery.get_upstreams_unsafe()
    upstreams['no_retry_error'] = Upstream('no_retry_error', {}, [get_server(handler, 'broken')])

    result = await handler.post_url('no_retry_error', handler.path)
    if result.error and result.status_code == 500:
        handler.text = 'no retry error'
    else:
        handler.text = result.data

    check_all_requests_done(handler, 'no_retry_error')


@router.post('/no_retry_error', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

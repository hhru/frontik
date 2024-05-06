from http_client.balancing import Upstream
from http_client.request_response import NoAvailableServerException

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/no_available_backend', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['no_available_backend'] = Upstream('no_available_backend', {}, [])

    request = handler.post_url('no_available_backend', handler.path)
    check_all_requests_done(handler, 'no_available_backend')

    result = await request

    if result.exc is not None and isinstance(result.exc, NoAvailableServerException):
        handler.text = 'no backend available'
        return

    handler.text = result.text

    check_all_requests_done(handler, 'no_available_backend')


@router.post('/no_available_backend', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

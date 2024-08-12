from http_client.balancing import Upstream

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from tests.projects.balancer_app import get_server


@plain_router.get('/speculative_no_retry', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['speculative_no_retry'] = Upstream(
        'speculative_no_retry',
        {},
        [get_server(handler, 'broken'), get_server(handler, 'normal')],
    )

    result = await handler.post_url(
        'speculative_no_retry',
        handler.path,
        connect_timeout=0.1,
        request_timeout=0.5,
        max_timeout_tries=1,
        speculative_timeout_pct=0.10,
    )

    if result.failed or result.status_code == 500:
        handler.text = 'no retry'
        return

    handler.text = result.data


@plain_router.post('/speculative_no_retry', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

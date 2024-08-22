from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from tests.projects.balancer_app import get_server


@plain_router.get('/speculative_retry', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstreams = handler.application.service_discovery.get_upstreams_unsafe()
    upstreams['speculative_retry'] = Upstream(
        'speculative_retry',
        {},
        [get_server(handler, 'broken'), get_server(handler, 'normal')],
    )

    result = await handler.put_url(
        'speculative_retry',
        handler.path,
        connect_timeout=0.1,
        request_timeout=0.5,
        max_timeout_tries=1,
        speculative_timeout_pct=0.1,
    )

    if result.failed or result.data is None:
        raise HTTPError(500)

    handler.text = result.data


@plain_router.put('/speculative_retry', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

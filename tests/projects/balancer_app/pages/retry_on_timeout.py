from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


@plain_router.get('/retry_on_timeout', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['retry_on_timeout'] = Upstream(
        'retry_on_timeout',
        {},
        [get_server(handler, 'broken'), get_server(handler, 'normal')],
    )

    result = await handler.delete_url(
        'retry_on_timeout',
        handler.path,
        connect_timeout=0.1,
        request_timeout=0.3,
        max_timeout_tries=2,
    )

    if result.error or result.data is None:
        raise HTTPError(500)

    handler.text = result.data

    check_all_requests_done(handler, 'retry_on_timeout')


@plain_router.delete('/retry_on_timeout', cls=PageHandler)
async def delete_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

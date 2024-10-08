from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


@plain_router.get('/retry_connect', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    upstreams = handler.application.service_discovery.get_upstreams_unsafe()
    upstreams['retry_connect'] = Upstream(
        'retry_connect',
        {},
        [get_server(handler, 'free'), get_server(handler, 'normal')],
    )
    handler.text = ''

    requests = [
        handler.post_url('retry_connect', handler.path),
        handler.post_url('retry_connect', handler.path),
        handler.post_url('retry_connect', handler.path),
    ]
    results = await gather_list(*requests)

    check_all_servers_were_occupied(handler, 'retry_connect')

    for result in results:
        if result.failed or result.data is None:
            raise HTTPError(500)

        handler.text = handler.text + result.data


@plain_router.post('/retry_connect', cls=PageHandler)
async def post_page(handler: PageHandler = get_current_handler()) -> None:
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

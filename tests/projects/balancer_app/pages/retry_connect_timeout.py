from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


@plain_router.get('/retry_connect_timeout', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['retry_connect_timeout'] = Upstream('retry_connect_timeout', {}, [get_server(handler, 'normal')])
    handler.text = ''

    requests = [
        handler.post_url('retry_connect_timeout', handler.path),
        handler.post_url('retry_connect_timeout', handler.path),
        handler.post_url('retry_connect_timeout', handler.path),
    ]
    results = await gather_list(*requests)

    check_all_servers_were_occupied(handler, 'retry_connect_timeout')

    for result in results:
        if result.error or result.data is None:
            raise HTTPError(500)

        handler.text = handler.text + result.data


@plain_router.post('/retry_connect_timeout', cls=PageHandler)
async def post_page(handler: PageHandler = get_current_handler()) -> None:
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

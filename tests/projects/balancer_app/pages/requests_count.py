import asyncio

from http_client.balancing import Upstream

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


@plain_router.get('/requests_count', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['requests_count_async'] = Upstream('requests_count_async', {}, [get_server(handler, 'normal')])
    handler.text = ''

    result1 = handler.post_url('requests_count_async', handler.path)
    result2 = handler.post_url('requests_count_async', handler.path)
    upstreams['requests_count_async'].update(Upstream('requests_count_async', {}, [get_server(handler, 'normal')]))
    result3 = handler.post_url('requests_count_async', handler.path)

    await asyncio.sleep(0)

    check_all_servers_occupied(handler, 'requests_count_async')

    _, _, response = await asyncio.gather(result1, result2, result3)

    handler.text = response.data

    check_all_requests_done(handler, 'requests_count_async')


@plain_router.post('/requests_count', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    upstreams = handler.application.upstream_manager.get_upstreams()
    servers = upstreams['requests_count_async'].servers
    handler.text = str(servers[0].stat_requests)

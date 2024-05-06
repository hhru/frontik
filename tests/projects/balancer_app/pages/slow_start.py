import asyncio

from http_client.balancing import Server, Upstream, UpstreamConfig

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_were_occupied


@router.get('/slow_start', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    server = get_server(handler, 'normal')
    server.weight = 5

    same_server = get_server(handler, 'normal')
    same_server.weight = 5

    server_slow_start = Server('127.0.0.1:12345', weight=5, dc='Test')

    upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0.1)}
    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['slow_start'] = Upstream('slow_start', upstream_config, [server])
    handler.text = ''

    await handler.post_url('slow_start', handler.path)

    await asyncio.sleep(0.2)
    upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=1)}
    upstreams['slow_start'].update(Upstream('slow_start', upstream_config, [same_server, server_slow_start]))

    await handler.post_url('slow_start', handler.path)

    await asyncio.sleep(1)

    requests = [handler.post_url('slow_start', handler.path), handler.post_url('slow_start', handler.path)]
    await asyncio.gather(*requests)

    check_all_servers_were_occupied(handler, 'slow_start')

    handler.text = str(server.stat_requests + server_slow_start.stat_requests)
    check_all_requests_done(handler, 'slow_start')


@router.post('/slow_start', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    upstreams = handler.application.upstream_manager.get_upstreams()
    handler.text = str(upstreams['slow_start'].servers[0].stat_requests)

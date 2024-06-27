from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik.handler import PageHandler

noop_upstream = Upstream('', {}, [])


def check_all_servers_occupied(handler: PageHandler, name: str) -> None:
    servers = handler.application.upstream_manager.get_upstreams().get(name, noop_upstream).servers
    if any(server.current_requests == 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')


def check_all_requests_done(handler: PageHandler, name: str) -> None:
    servers = handler.application.upstream_manager.get_upstreams().get(name, noop_upstream).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPError(500, 'some servers have unfinished requests')


def check_all_servers_were_occupied(handler: PageHandler, name: str) -> None:
    servers = handler.application.upstream_manager.get_upstreams().get(name, noop_upstream).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')
    if any(server.stat_requests == 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')

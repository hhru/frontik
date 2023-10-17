from tornado.web import HTTPError

from frontik.handler import PageHandler


def check_all_servers_occupied(handler: PageHandler, name: str) -> None:
    servers = handler.application.upstream_manager.upstreams.get(name).servers
    if any(server.current_requests == 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')


def check_all_requests_done(handler: PageHandler, name: str) -> None:
    servers = handler.application.upstream_manager.upstreams.get(name).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPError(500, 'some servers have unfinished requests')


def check_all_servers_were_occupied(handler: PageHandler, name: str) -> None:
    servers = handler.application.upstream_manager.upstreams.get(name).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')
    if any(server.stat_requests == 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')

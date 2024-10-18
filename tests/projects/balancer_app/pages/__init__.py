from fastapi import Request
from http_client.balancing import Upstream
from tornado.web import HTTPError

noop_upstream = Upstream('', {}, [])


def check_all_servers_occupied(request: Request, name: str) -> None:
    servers = request.app.service_discovery.get_upstreams_unsafe().get(name, noop_upstream).servers
    if any(server.current_requests == 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')


def check_all_requests_done(request: Request, name: str) -> None:
    servers = request.app.service_discovery.get_upstreams_unsafe().get(name, noop_upstream).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPError(500, 'some servers have unfinished requests')


def check_all_servers_were_occupied(request: Request, name: str) -> None:
    servers = request.app.service_discovery.get_upstreams_unsafe().get(name, noop_upstream).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')
    if any(server.stat_requests == 0 for server in servers):
        raise HTTPError(500, 'some servers are ignored')

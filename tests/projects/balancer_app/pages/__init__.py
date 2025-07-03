from fastapi import HTTPException, Request
from http_client.balancing import Upstream, UpstreamConfigs

noop_upstream = Upstream('', UpstreamConfigs({}), [])


def check_all_servers_occupied(request: Request, name: str) -> None:
    servers = request.app.service_discovery.get_upstream(name, noop_upstream).servers
    if any(server.current_requests == 0 for server in servers):
        raise HTTPException(500, 'some servers are ignored')


def check_all_requests_done(request: Request, name: str) -> None:
    servers = request.app.service_discovery.get_upstream(name, noop_upstream).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPException(500, 'some servers have unfinished requests')


def check_all_servers_were_occupied(request: Request, name: str) -> None:
    servers = request.app.service_discovery.get_upstream(name, noop_upstream).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPException(500, 'some servers are ignored')
    if any(server.stat_requests == 0 for server in servers):
        raise HTTPException(500, 'some servers are ignored')

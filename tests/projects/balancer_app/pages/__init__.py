from tornado.web import HTTPError


def check_all_servers_occupied(handler, name):
    servers = handler._http_client.upstreams.get(name).servers
    if any(server.current_requests == 0 for server in servers):
        raise HTTPError(500, 'some servers is ignored')


def check_all_requests_done(handler, name):
    servers = handler._http_client.upstreams.get(name).servers
    if any(server.current_requests != 0 for server in servers):
        raise HTTPError(500, 'some servers has not finished requests')

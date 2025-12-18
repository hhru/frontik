from fastapi import Request
from http_client.balancing import Upstream, UpstreamConfigs
from http_client.exceptions import NoAvailableServerError

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/no_available_backend')
async def get_page(request: Request, http_client: HttpClient) -> str:
    upstreams = request.app.service_discovery._upstreams
    no_available_backend = 'no_available_backend'
    upstreams[no_available_backend] = Upstream(no_available_backend, UpstreamConfigs({}), [])

    req = http_client.post_url(no_available_backend, no_available_backend)
    check_all_requests_done(request, no_available_backend)

    result = await req

    if result.exc is not None and isinstance(result.exc, NoAvailableServerError):
        return 'no backend available'

    check_all_requests_done(request, no_available_backend)
    return result.text


@router.post('/no_available_backend')
async def post_page():
    return 'result'

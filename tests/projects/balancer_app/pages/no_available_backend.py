from http_client.balancing import Upstream
from http_client.request_response import NoAvailableServerException

from fastapi import Request

from frontik.dependencies import HttpClientT
from frontik.routing import router
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/no_available_backend')
async def get_page(request: Request, http_client: HttpClientT):
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    upstreams['no_available_backend'] = Upstream('no_available_backend', {}, [])

    u = request.url
    request = http_client.post_url('no_available_backend', u.path + '?' + u.query)
    check_all_requests_done(request, 'no_available_backend')

    result = await request

    if result.exc is not None and isinstance(result.exc, NoAvailableServerException):
        return 'no backend available'

    check_all_requests_done(request, 'no_available_backend')
    return result.text


@router.post('/no_available_backend')
async def post_page():
    return 'result'

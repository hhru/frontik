from fastapi import Request
from http_client.balancing import Upstream, UpstreamConfig, UpstreamConfigs
from http_client.model.consul_config import RetryPolicyItem
from tornado.web import HTTPError

from frontik.dependencies import HttpClient
from frontik.routing import router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/retry_non_idempotent_503')
async def get_page(request: Request, http_client: HttpClient) -> str:
    upstream_config = {
        Upstream.DEFAULT_PROFILE: UpstreamConfig(retry_policy={503: RetryPolicyItem(retry_non_idempotent=True)})
    }
    upstreams = request.app.service_discovery._upstreams
    retry_non_idempotent = 'retry_non_idempotent_503'
    upstreams[retry_non_idempotent] = Upstream(
        retry_non_idempotent,
        UpstreamConfigs(upstream_config),
        [get_server(request, 'broken'), get_server(request, 'normal')],
    )
    upstreams['do_not_retry_non_idempotent_503'] = Upstream(
        'do_not_retry_non_idempotent_503',
        UpstreamConfigs({}),
        [get_server(request, 'broken'), get_server(request, 'normal')],
    )

    res1, res2 = await gather_list(
        http_client.post_url(retry_non_idempotent, retry_non_idempotent),
        http_client.post_url('do_not_retry_non_idempotent_503', retry_non_idempotent),
    )

    if res1.error or res1.data is None:
        raise HTTPError(500)
    text = res1.data

    if res2.status_code != 503:
        raise HTTPError(500)

    check_all_requests_done(request, retry_non_idempotent)
    check_all_requests_done(request, 'do_not_retry_non_idempotent_503')

    return text


@router.post('/retry_non_idempotent_503')
async def post_page() -> str:
    return 'result'

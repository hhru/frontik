from http_client.balancing import Upstream, UpstreamConfig
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


@plain_router.get('/retry_non_idempotent_503', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(retry_policy={503: {'idempotent': 'true'}})}
    upstreams = handler.application.service_discovery.get_upstreams_unsafe()
    upstreams['retry_non_idempotent_503'] = Upstream(
        'retry_non_idempotent_503',
        upstream_config,
        [get_server(handler, 'normal')],
    )
    upstreams['do_not_retry_non_idempotent_503'] = Upstream(
        'do_not_retry_non_idempotent_503',
        {},
        [get_server(handler, 'broken')],
    )

    res1, res2 = await gather_list(
        handler.post_url('retry_non_idempotent_503', handler.path),
        handler.post_url('do_not_retry_non_idempotent_503', handler.path),
    )

    if res1.error or res1.data is None:
        raise HTTPError(500)
    handler.text = res1.data

    if res2.status_code != 503:
        raise HTTPError(500)

    check_all_requests_done(handler, 'retry_non_idempotent_503')
    check_all_requests_done(handler, 'do_not_retry_non_idempotent_503')


@plain_router.post('/retry_non_idempotent_503', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'

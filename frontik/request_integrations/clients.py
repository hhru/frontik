from contextlib import contextmanager

from frontik import request_context
from frontik.options import options
from frontik.request_integrations.integrations_dto import IntegrationDto
from frontik.util import check_request_id, generate_uniq_timestamp_request_id
from frontik.dependencies import clients

@contextmanager
def clients_ctx(_frontik_app, _tornado_request):
    token = clients.set({})
    try:
        yield IntegrationDto()
    finally:
        clients.reset(token)

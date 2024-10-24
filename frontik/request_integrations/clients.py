from contextlib import contextmanager

from frontik.dependencies import clients
from frontik.request_integrations.integrations_dto import IntegrationDto


@contextmanager
def clients_ctx(_frontik_app, _tornado_request):
    token = clients.set({})
    try:
        yield IntegrationDto()
    finally:
        clients.reset(token)

from contextlib import contextmanager

from frontik import request_context
from frontik.options import options
from frontik.request_integrations.integrations_dto import IntegrationDto
from frontik.util import check_request_id, generate_uniq_timestamp_request_id


@contextmanager
def request_id_ctx(_, tornado_request):
    request_id = tornado_request.headers.get('X-Request-Id') or generate_uniq_timestamp_request_id()
    if options.validate_request_id:
        check_request_id(request_id)
    tornado_request.request_id = request_id

    token = request_context._context.set(request_context._Context(request_id))
    try:
        yield IntegrationDto()
    finally:
        request_context._context.reset(token)

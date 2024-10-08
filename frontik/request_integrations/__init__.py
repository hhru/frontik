from frontik.request_integrations.request_id import request_id_ctx
from frontik.request_integrations.request_limiter import request_limiter
from frontik.request_integrations.server_timing import server_timing
from frontik.request_integrations.telemetry import otel_instrumentation_ctx

_integrations: list = [
    ('request_id', request_id_ctx),
    ('request_limiter', request_limiter),
    ('server_timing', server_timing),
    ('telemetry', otel_instrumentation_ctx),
]


def get_integrations() -> list:
    return _integrations
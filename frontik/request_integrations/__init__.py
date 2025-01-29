from frontik.request_integrations import request_context, request_limiter
from frontik.request_integrations.telemetry import otel_instrumentation_ctx

_integrations: list = [
    ('request_context', request_context.request_context),
    ('request_limiter', request_limiter.request_limiter),
    ('telemetry', otel_instrumentation_ctx),
]


def get_integrations() -> list:
    return _integrations

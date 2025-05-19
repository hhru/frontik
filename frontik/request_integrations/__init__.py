from frontik.request_integrations import request_context, request_limiter
from frontik.request_integrations.sentry import sentry_context
from frontik.request_integrations.telemetry import otel_instrumentation_ctx

_integrations: list = [
    ('request_context', request_context.request_context),
    ('request_limiter', request_limiter.request_limiter),
    ('telemetry', otel_instrumentation_ctx),
    ('sentry', sentry_context),
]


def get_integrations() -> list:
    return _integrations

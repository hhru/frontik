from typing import Any

from frontik.app_integrations.statsd import StatsDClient
from frontik.dependencies import clients


def count(aspect: str, delta: int, **kwargs: Any) -> None:
    _statsd_client: StatsDClient = clients.get().get('statsd_client')
    return _statsd_client.count(aspect, delta, **kwargs)


def gauge(aspect: str, value: float, **kwargs: Any) -> None:
    _statsd_client: StatsDClient = clients.get().get('statsd_client')
    return _statsd_client.gauge(aspect, value, **kwargs)


def time(aspect: str, value: float, **kwargs: Any) -> None:
    _statsd_client: StatsDClient = clients.get().get('statsd_client')
    return _statsd_client.time(aspect, value, **kwargs)

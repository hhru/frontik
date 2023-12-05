from datetime import timedelta

ServiceTimeout = timedelta | float | None


def timeout_seconds(timeout: ServiceTimeout) -> float:
    if isinstance(timeout, float):
        return timeout
    return timeout.total_seconds() if timeout is not None else None

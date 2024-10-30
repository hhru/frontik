import contextvars
from typing import Any

clients: contextvars.ContextVar = contextvars.ContextVar('clients')


def get_app_config() -> Any:
    return clients.get().get('app_config')

from __future__ import annotations
import importlib
import logging
import pkgutil
from asyncio import Future
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frontik.app import FrontikApplication
    from frontik.handler import PageHandler

integrations_logger = logging.getLogger('integrations')


class Integration:
    def initialize_app(self, app: FrontikApplication) -> Future|None:
        raise NotImplementedError()  # pragma: no cover

    def deinitialize_app(self, app: FrontikApplication) -> Future|None:
        pass  # pragma: no cover

    def initialize_handler(self, handler: PageHandler) -> None:
        raise NotImplementedError()  # pragma: no cover


def load_integrations(app: FrontikApplication) -> tuple[list[Integration], list[Future]]:
    for importer, module_name, is_package in pkgutil.iter_modules(__path__):
        try:
            importlib.import_module(f'frontik.integrations.{module_name}')
        except Exception as e:
            integrations_logger.info('%s integration is not available: %s', module_name, e)

    available_integrations = []
    init_futures = []

    for integration_class in Integration.__subclasses__():
        integration = integration_class()
        init_future = integration.initialize_app(app)
        if init_future is not None:
            init_futures.append(init_future)

        available_integrations.append(integration)

    return available_integrations, init_futures

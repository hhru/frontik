import importlib
import logging
import pkgutil
from asyncio import Future
from typing import List, Optional, Tuple

integrations_logger = logging.getLogger('integrations')


def load_integrations(app) -> Tuple[List['Integration'], List[Future]]:
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


class Integration:
    def initialize_app(self, app) -> Optional[Future]:
        raise NotImplementedError()  # pragma: no cover

    def deinitialize_app(self, app) -> Optional[Future]:
        pass  # pragma: no cover

    def initialize_handler(self, handler):
        raise NotImplementedError()  # pragma: no cover

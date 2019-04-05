import importlib
import logging
import pkgutil
from typing import List

integrations_logger = logging.getLogger('integrations')


def load_integrations(app) -> List['Integration']:
    for importer, module_name, is_package in pkgutil.iter_modules(__path__):
        try:
            importlib.import_module(f'frontik.integrations.{module_name}')
        except Exception as e:
            integrations_logger.info('%s integration is not available: %s', module_name, e)

    available_integrations = []

    for integration_class in Integration.__subclasses__():
        integration = integration_class()
        integration.initialize_app(app)
        available_integrations.append(integration)

    return available_integrations


class Integration:
    def initialize_app(self, app):
        raise NotImplementedError()  # pragma: no cover

    def initialize_handler(self, handler):
        raise NotImplementedError()  # pragma: no cover

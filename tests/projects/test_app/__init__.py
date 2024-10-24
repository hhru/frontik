import logging

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_logger
from tests.projects.test_app import config


class TestApplication(FrontikApplication):
    def __init__(self):
        bootstrap_logger('custom_logger', logging.DEBUG, False)
        super().__init__()

    def application_config(self):
        return config

    def application_version_xml(self):
        return config.version

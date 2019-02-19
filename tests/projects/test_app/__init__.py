import logging

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_logger
from frontik.options import options

from tests.projects.test_app import config


class TestApplication(FrontikApplication):
    def __init__(self, **settings):
        options.sentry_dsn = 'http://key:secret@127.0.0.1:{}/sentry'.format(settings['port'])

        bootstrap_logger('custom_logger', logging.DEBUG, False)

        super().__init__(**settings)

    def application_config(self):
        return config

    def application_version_xml(self):
        return config.version

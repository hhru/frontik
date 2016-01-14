# coding=utf-8

from frontik.app import FrontikApplication

from tests.projects.test_app import config


class TestApplication(FrontikApplication):
    def __init__(self, **settings):
        settings['sentry_dsn'] = 'http://key:secret@127.0.0.1:{}/sentry'.format(settings['port'])

        super(TestApplication, self).__init__(**settings)

    def application_config(self):
        return config

    def application_version_xml(self):
        return config.version

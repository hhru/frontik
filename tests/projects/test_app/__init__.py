# coding=utf-8

from frontik.app import FrontikApplication

from tests.projects.test_app import config


class TestApplication(FrontikApplication):
    def application_config(self):
        return config

    def application_version_xml(self):
        return config.version

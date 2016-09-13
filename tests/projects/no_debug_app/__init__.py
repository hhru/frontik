# coding=utf-8

from frontik.app import FrontikApplication

from tests.projects.no_debug_app import config


class TestApplication(FrontikApplication):
    def application_config(self):
        return config

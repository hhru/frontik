# coding=utf-8

from frontik.app import FrontikApplication

from tests.projects.re_app import config


class TestApplication(FrontikApplication):
    def application_config(self):
        return config

    def application_urls(self):
        return config.urls

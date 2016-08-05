# coding=utf-8

from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    def __init__(self, **settings):
        super(TestApplication, self).__init__(**settings)

from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    def application_config(self):
        from . import config
        return config

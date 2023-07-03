from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    def application_config(self):
        from tests.projects.broken_config_app import config
        return config

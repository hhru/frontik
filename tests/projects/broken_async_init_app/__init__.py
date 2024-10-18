from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    def init(self):
        raise Exception('broken async init')

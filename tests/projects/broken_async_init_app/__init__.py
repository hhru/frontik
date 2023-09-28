from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    def init(self):
        msg = 'broken async init'
        raise Exception(msg)

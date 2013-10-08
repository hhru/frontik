class FutureVal(object):
    def get(self):
        pass


class Placeholder(FutureVal):
    def __init__(self):
        self.data = None

    def set_data(self, data):
        self.data = data

    def get(self):
        return self.data

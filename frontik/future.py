# coding=utf-8


class FailedFutureException(Exception):
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)


class FutureVal(object):
    __slots__ = ()

    def get(self):
        pass


class Placeholder(FutureVal):
    __slots__ = ('data',)

    def __init__(self):
        self.data = None

    def set_data(self, data):
        self.data = data

    def get(self):
        if isinstance(self.data, FailedFutureException):
            raise self.data
        return self.data

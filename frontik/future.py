# coding=utf-8


class FutureStateException(Exception):
    pass


class Placeholder(object):
    __slots__ = ('_data', '_finished', '_callbacks')

    def __init__(self):
        self._data = None
        self._finished = False
        self._callbacks = []

    def set_data(self, data):
        if self._finished:
            raise FutureStateException('Data has already been set')

        self._finished = True
        self._data = data

        for callback in self._callbacks:
            callback(self._data)

    def get(self):
        return self._data

    def add_data_callback(self, callback):
        if not self._finished:
            self._callbacks.append(callback)
        else:
            callback(self._data)

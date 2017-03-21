# coding=utf-8

import threading


class RequestContext(object):
    _state = threading.local()
    _state.data = {}

    def __init__(self, data):
        self._data = data

    @classmethod
    def get(cls, param):
        if not hasattr(cls._state, 'data'):
            cls._state.data = {}

        return cls._state.data.get(param)

    @classmethod
    def set(cls, param, value):
        if not hasattr(cls._state, 'data'):
            cls._state.data = {}

        cls._state.data[param] = value

    def __enter__(self):
        self._prev_data = getattr(self.__class__._state, 'data', {})
        self.__class__._state.data = self._data

    def __exit__(self, *exc):
        self.__class__._state.data = self._prev_data
        return False

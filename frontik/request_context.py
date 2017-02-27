import threading


class RequestContext(object):
    _state = threading.local()
    _state.data = {}

    def __init__(self, data):
        self._data = data

    @classmethod
    def get_data(cls):
        return getattr(cls._state, 'data', {})

    def __enter__(self):
        self._prev_data = getattr(self.__class__._state, 'data', {})
        self.__class__._state.data = self._data

    def __exit__(self, *exc):
        self.__class__._state.data = self._prev_data
        del self._prev_data
        return False

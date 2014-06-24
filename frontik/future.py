# coding=utf-8


class FutureStateException(Exception):
    pass


class Future(object):
    __slots__ = ('_result', '_finished', '_callbacks')

    def __init__(self):
        self._result = None
        self._finished = False
        self._callbacks = []

    def set_result(self, result):
        if self._finished:
            raise FutureStateException('Result has already been set')

        self._finished = True
        self._result = result

        for callback in self._callbacks:
            callback(self._result)

    # deprecated synonym
    set_data = set_result

    def result(self):
        return self._result

    # deprecated synonym
    get = result

    def add_done_callback(self, callback):
        if not self._finished:
            self._callbacks.append(callback)
        else:
            callback(self._result)

# deprecated synonym
Placeholder = Future

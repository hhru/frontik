# coding=utf-8


class FutureStateException(Exception):
    pass


class Future(object):
    __slots__ = ('_result', '_done', '_callbacks')

    def __init__(self):
        self._result = None
        self._done = False
        self._callbacks = []

    def set_result(self, result):
        if self._done:
            raise FutureStateException('Result has already been set')

        self._result = result
        self._set_done()

    # deprecated synonym
    set_data = set_result

    def result(self):
        return self._result

    # deprecated synonym
    get = result

    def add_done_callback(self, callback):
        if not self._done:
            self._callbacks.append(callback)
        else:
            callback(self._result)

    def _set_done(self):
        self._done = True
        for callback in self._callbacks:
            callback(self._result)  # Tornado Future does callback(self)
        self._callbacks = None

# deprecated synonym
Placeholder = Future

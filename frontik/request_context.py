import threading


class RequestContext:
    """Keeps track of current request data.

    Usage::

    ```
    with StackContext(partial(RequestContext, {'data_key': data_value})):
        IOLoop.add_callback(do_something)

    def do_something():
        print(RequestContext.get('data_key'))
    ```

    `RequestContext` is initialized at the beginning of request handling
    and can be populated with neccessary data at any time.

    `RequestContext` is not passed automatically to other threads
    and it probably shouldn't due to StackContext being not thread-safe
    (see https://github.com/tornadoweb/tornado/pull/1618).
    """

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
        del self._prev_data
        return False

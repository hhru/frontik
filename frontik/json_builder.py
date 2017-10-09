# coding=utf-8

import json

from tornado.concurrent import Future

from frontik.compat import basestring_type, iteritems


def _encode_value(v):
    def _encode_iterable(l):
        return [_encode_value(v) for v in l]

    def _encode_dict(d):
        return {k: _encode_value(v) for k, v in iteritems(d)}

    if isinstance(v, dict):
        return _encode_dict(v)

    elif isinstance(v, (set, frozenset, list, tuple)):
        return _encode_iterable(v)

    elif isinstance(v, Future):
        if v.done():
            return _encode_value(v.result())

        return None

    elif hasattr(v, 'to_dict'):
        return v.to_dict()

    return v


class FrontikJsonEncoder(json.JSONEncoder):
    """
    This encoder supports additional value types:
    * sets and frozensets
    * datetime.date objects
    * objects with `to_dict()` method
    * objects with `to_json_value()` method
    * `Future` objects (only if the future is resolved)
    """
    def default(self, obj):
        return _encode_value(obj)


class JsonBuilder(object):
    __slots__ = ('_data', '_encoder', 'root_node')

    def __init__(self, root_node=None, json_encoder=None):
        if root_node is not None and not isinstance(root_node, basestring_type):
            raise TypeError('Cannot set {} as root node'.format(root_node))

        self._data = []
        self._encoder = json_encoder
        self.root_node = root_node

    def put(self, *args, **kwargs):
        """Append a chunk of data to JsonBuilder."""
        self._data.extend(args)
        if kwargs:
            self._data.append(kwargs)

    def is_empty(self):
        return len(self._data) == 0

    def clear(self):
        self._data = []

    def replace(self, *args, **kwargs):
        self.clear()
        self.put(*args, **kwargs)

    def to_dict(self):
        """ Return plain dict from all data appended to JsonBuilder """
        return _encode_value(self._concat_chunks())

    def _concat_chunks(self):
        result = {}
        for chunk in self._data:
            if isinstance(chunk, Future) or hasattr(chunk, 'to_dict'):
                chunk = _encode_value(chunk)

            if chunk is not None:
                result.update(chunk)

        if self.root_node is not None:
            result = {self.root_node: result}

        return result

    def to_string(self):
        if self._encoder is None:
            return json.dumps(self._concat_chunks(), cls=FrontikJsonEncoder, ensure_ascii=False)

        if issubclass(self._encoder, FrontikJsonEncoder):
            return json.dumps(self._concat_chunks(), cls=self._encoder, ensure_ascii=False)

        # For backwards compatibility, remove when all encoders extend FrontikJsonEncoder
        return json.dumps(self.to_dict(), cls=self._encoder, ensure_ascii=False)

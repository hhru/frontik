# coding=utf-8

import collections
import json

import frontik.future


class JsonBuilder(object):
    __slots__ = ('_data', '_encoder', 'root_node_name')

    def __init__(self, root_node_name=None, json_encoder=None):
        self._data = []
        self._encoder = json_encoder
        self.root_node_name = root_node_name

    def put(self, *args, **kwargs):
        self._data.extend(args)
        if kwargs:
            self._data.append(kwargs)

    def is_empty(self):
        return len(self._data) == 0

    def clear(self):
        self._data = []

    @staticmethod
    def get_error_node(response):
        return {
            'error': {
                'reason': str(response.error),
                'code': response.code
            }
        }

    def _check_value(self, v):
        def _check_iterable(l):
            return [self._check_value(v) for v in l]

        def _check_dict(d):
            return dict((k, self._check_value(v)) for k, v in d.iteritems())

        if isinstance(v, dict):
            return _check_dict(v)
        elif isinstance(v, (set, list, tuple)):
            return _check_iterable(v)
        elif isinstance(v, frontik.future.FutureVal):
            return self._check_value(v.get())
        elif isinstance(v, frontik.future.FailedFutureException):
            return self.get_error_node(v)
        elif isinstance(v, JsonBuilder):
            return _check_dict(v.to_dict())

        return v

    def to_dict(self):
        result = {}
        for chunk in self._check_value(self._data):
            if chunk is not None:
                result.update(chunk)

        if self.root_node_name is not None:
            result = {self.root_node_name: result}

        return result

    def to_string(self):
        if self._encoder is not None:
            return json.dumps(self.to_dict(), cls=self._encoder)
        return json.dumps(self.to_dict())

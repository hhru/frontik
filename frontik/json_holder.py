# coding=utf-8

import json
from json import JSONEncoder

import frontik.future


class NestedFutureEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, frontik.future.FutureVal):
            value = o.get()
            if isinstance(value, frontik.future.FailedFutureException):
                return JsonHolder.get_error_node(value)
            return value
        elif isinstance(o, frontik.future.FailedFutureException):
            return JsonHolder.get_error_node(o)
        return JSONEncoder.default(self, o)


class JsonHolder(object):
    __slots__ = ('_data', '_list_mode')

    def __init__(self):
        self._data = []
        self._list_mode = False

    def put(self, chunk, key_name=None):
        if key_name is not None:
            chunk = {key_name: chunk}

        elif isinstance(chunk, list):
            if self._data and not self._list_mode:
                raise ValueError('Cannot extend JSON dict with a list')

            self._list_mode = True
            self._data.extend(chunk)
            return

        self._data.append(chunk)

    def is_empty(self):
        return len(self._data) == 0

    @staticmethod
    def get_error_node(response):
        return {
            'error': {
                'url': response.effective_url,
                'reason': response.error,
                'code': response.code
            }
        }

    def to_list(self):
        if not self._list_mode:
            return [self._data]
        return self._data

    def to_dict(self):
        assert not self._list_mode, 'Cannot covert JSON list to dict'

        result = {}
        for chunk in self._data:
            if isinstance(chunk, frontik.future.FutureVal):
                value = chunk.get()

                if isinstance(value, frontik.future.FailedFutureException):
                    result.update(self.get_error_node(value))
                elif value is not None:
                    result.update(value)

            elif chunk is not None:
                result.update(chunk)

        return result

    def to_string(self):
        return json.dumps(self.to_list() if self._list_mode else self.to_dict(), cls=NestedFutureEncoder)

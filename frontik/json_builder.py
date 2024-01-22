from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional, Union

import orjson
from pydantic import BaseModel
from tornado.concurrent import Future

if TYPE_CHECKING:
    from typing import Any

handler_logger = logging.getLogger('handler')


FrontikJsonDecodeError = orjson.JSONDecodeError


def _encode_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _encode_value(v) for k, v in value.items()}

    elif isinstance(value, (set, frozenset, list, tuple)):
        return [_encode_value(v1) for v1 in value]

    elif isinstance(value, Future):
        if value.done() and value.exception() is None:
            return _encode_value(value.result())

        return None

    elif isinstance(value, BaseModel):
        return value.model_dump()

    elif hasattr(value, 'to_dict'):
        return value.to_dict()

    return value


def json_encode(obj: Any, default: Callable = _encode_value) -> str:
    return orjson.dumps(obj, default=default, option=orjson.OPT_NON_STR_KEYS).decode('utf-8')


def json_decode(value: Union[str, bytes]) -> Any:
    return orjson.loads(value)


class JsonBuilder:
    __slots__ = ('_data', '_encoder', 'root_node')

    def __init__(self, root_node: Optional[str] = None, json_encoder: Optional[Callable] = None) -> None:
        if root_node is not None and not isinstance(root_node, str):
            msg = f'Cannot set {root_node} as root node'
            raise TypeError(msg)

        self._data: list = []
        self._encoder = json_encoder
        self.root_node = root_node

    def put(self, *args: Any, **kwargs: Any) -> None:
        """Append a chunk of data to JsonBuilder."""
        self._data.extend(args)
        if kwargs:
            self._data.append(kwargs)

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def clear(self) -> None:
        self._data = []

    def replace(self, *args: Any, **kwargs: Any) -> None:
        self.clear()
        self.put(*args, **kwargs)

    def to_dict(self) -> dict:
        """Return plain dict from all data appended to JsonBuilder"""
        return _encode_value(self._concat_chunks())

    def _concat_chunks(self) -> dict:
        result = {}
        for chunk in self._data:
            if isinstance(chunk, Future) or hasattr(chunk, 'to_dict'):
                handler_logger.warning('Using handler.json.put(FUTURE) is bad, please use only json-compatible data')
                chunk = _encode_value(chunk)

            if chunk is not None:
                result.update(chunk)

        if self.root_node is not None:
            result = {self.root_node: result}

        return result

    def to_string(self) -> str:
        if self._encoder is None:
            return json_encode(self._concat_chunks())

        return json_encode(self._concat_chunks(), default=self._encoder)

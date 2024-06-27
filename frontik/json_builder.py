from __future__ import annotations

import logging
from typing import Annotated, Any, Callable, Optional, Union

import orjson
from fastapi import Depends, Request
from pydantic import BaseModel
from tornado.concurrent import Future

handler_logger = logging.getLogger('handler')

FrontikJsonDecodeError = orjson.JSONDecodeError


def _deep_encode_value(value: Any) -> Any:
    """
    This method partially duplicates ``_encode_value()``.

    It is only used by ``JsonBuilder.to_dict()``
    which is only used by ``JsonProducer.get_jinja_context()``.
    """

    if isinstance(value, dict):
        return {k: _deep_encode_value(v) for k, v in value.items()}

    elif isinstance(value, (set, frozenset, list, tuple)):
        return [_deep_encode_value(v1) for v1 in value]

    elif isinstance(value, Future):
        if value.done() and value.exception() is None:
            return _deep_encode_value(value.result())

        return None

    elif isinstance(value, BaseModel):
        return _deep_encode_value(value.model_dump())

    elif hasattr(value, 'to_dict'):
        return _deep_encode_value(value.to_dict())

    return value


def _encode_value(value: Any) -> Any:
    if isinstance(value, (set, frozenset)):
        return list(value)

    elif isinstance(value, Future):
        if value.done() and value.exception() is None:
            return value.result()

        return None

    elif isinstance(value, BaseModel):
        return value.model_dump()

    elif hasattr(value, 'to_dict'):
        return value.to_dict()

    raise TypeError


def json_encode_bytes(obj: Any, default: Callable = _encode_value) -> bytes:
    return orjson.dumps(obj, default=default, option=orjson.OPT_NON_STR_KEYS)


def json_encode(obj: Any, default: Callable = _encode_value) -> str:
    return json_encode_bytes(obj, default).decode('utf-8')


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
        return _deep_encode_value(self._concat_chunks())

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

    def to_bytes(self) -> bytes:
        return json_encode_bytes(self._concat_chunks())


def get_json_builder(request: Request) -> JsonBuilder:
    return request['json_builder']


JsonBuilderT = Annotated[JsonBuilder, Depends(get_json_builder)]

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

from tornado.concurrent import Future

if TYPE_CHECKING:
    from typing import Any

handler_logger = logging.getLogger('handler')


def _encode_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _encode_value(v) for k, v in value.items()}

    elif isinstance(value, (set, frozenset, list, tuple)):
        return [_encode_value(v1) for v1 in value]

    elif isinstance(value, Future):
        if value.done() and value.exception() is None:
            return _encode_value(value.result())

        return None

    elif hasattr(value, 'to_dict'):
        return value.to_dict()

    return value


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


class JsonBuilder:
    __slots__ = ('_data', '_encoder', 'root_node')

    def __init__(self, root_node: Optional[str] = None, json_encoder: Any = None) -> None:
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
            return json.dumps(self._concat_chunks(), cls=FrontikJsonEncoder, ensure_ascii=False)

        if issubclass(self._encoder, FrontikJsonEncoder):
            return json.dumps(self._concat_chunks(), cls=self._encoder, ensure_ascii=False)

        # For backwards compatibility, remove when all encoders extend FrontikJsonEncoder
        return json.dumps(self.to_dict(), cls=self._encoder, ensure_ascii=False)

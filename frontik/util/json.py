import logging
from typing import Any, Callable, Union

import orjson
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

    elif isinstance(value, bytes):
        return value.decode('utf-8')

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

    elif isinstance(value, bytes):
        return value.decode('utf-8')

    raise TypeError


def json_encode_bytes(obj: Any, default: Callable = _encode_value, sort_keys: bool = False) -> bytes:
    options = (
        (orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_SORT_KEYS)
        if sort_keys
        else (orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY)
    )
    return orjson.dumps(obj, default=default, option=options)


def json_encode(obj: Any, default: Callable = _encode_value, sort_keys: bool = False) -> str:
    return json_encode_bytes(obj, default, sort_keys).decode('utf-8')


def json_decode(value: Union[str, bytes]) -> Any:
    return orjson.loads(value)

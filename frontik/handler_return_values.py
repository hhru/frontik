from collections.abc import Callable, Collection
from typing import Any

import orjson
from pydantic import BaseModel

from frontik import media_types
from frontik.handler import PageHandler

ReturnedValue = Any
ReturnedValueHandler = Callable[[PageHandler, ReturnedValue], Any]
ReturnedValueHandlers = Collection[ReturnedValueHandler]


def write_json_response_from_dict(handler: PageHandler, value: Any) -> None:
    if isinstance(value, dict):
        handler.set_header('Content-Type', media_types.APPLICATION_JSON)
        handler.text = orjson.dumps(value).decode("utf-8")


def write_json_response_from_pydantic(handler: PageHandler, value: BaseModel) -> None:
    if isinstance(value, BaseModel):
        handler.set_header('Content-Type', media_types.APPLICATION_JSON)
        handler.text = value.model_dump_json()


def get_default_returned_value_handlers() -> ReturnedValueHandlers:
    return [
        write_json_response_from_dict,
        write_json_response_from_pydantic,
    ]

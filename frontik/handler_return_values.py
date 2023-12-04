from collections.abc import Callable, Collection
from typing import Any

from pydantic import BaseModel

from frontik import media_types
from frontik.handler import PageHandler

ReturnedValue = Any
ReturnedValueHandler = Callable[[ReturnedValue, PageHandler], Any]
ReturnedValueHandlers = Collection[ReturnedValueHandler]


def put_dict_to_json(value: Any, handler: PageHandler) -> None:
    if isinstance(value, dict):
        handler.set_header('Content-Type', media_types.APPLICATION_JSON)
        handler.json.put(value)


def put_pydantic_model_to_json(value: BaseModel, handler: PageHandler) -> None:
    if isinstance(value, BaseModel):
        handler.set_header('Content-Type', media_types.APPLICATION_JSON)
        handler.json.put(value.model_dump())


def get_default_returned_value_handlers() -> ReturnedValueHandlers:
    return [
        put_dict_to_json,
        put_pydantic_model_to_json,
    ]

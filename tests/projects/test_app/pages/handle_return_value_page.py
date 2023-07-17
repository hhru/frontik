from typing import Callable, Awaitable

from pydantic import BaseModel

from frontik import handler


class LocalTestModel(BaseModel):
    int_field: int
    str_field: str


class Page(handler.PageHandler):
    async def call_page_handler_method(
        self, page_handler_method: Callable[..., Awaitable]
    ):
        returned_value: BaseModel = await page_handler_method()
        self.finish(returned_value.json())

    async def get_page(self) -> LocalTestModel:
        return LocalTestModel(int_field=1, str_field='ne_int')

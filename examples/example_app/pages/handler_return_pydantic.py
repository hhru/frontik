from pydantic import BaseModel

import frontik.handler


class ResponseModel(BaseModel):
    str_field: str


class Page(frontik.handler.PageHandler):
    def get_page(self) -> ResponseModel:
        return ResponseModel(str_field='Привет')

from frontik.dependencies import http_client
from frontik.routing import router
from fastapi import FastAPI, File, UploadFile, Request
from typing import Annotated
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, ValueTarget
import json
from fastapi import HTTPException
from json import JSONDecodeError
from pydantic import BaseModel
from annotated_types import MaxLen


MAX_LEN_KEY = 100
MAX_LEN_VAL = 100

meta_info_key = Annotated[str, MaxLen(MAX_LEN_KEY)]
meta_info_val = Annotated[str, MaxLen(MAX_LEN_VAL)]

class MetaInfo(BaseModel):
    data: dict[meta_info_key, (float | int | bool | meta_info_val)] | None

#  ffile: UploadFile = File(alias='my_attachment')


@router.post('/example')
async def example_page(request: Request) -> dict:
    ffile = ValueTarget()

    parser = StreamingFormDataParser(headers=request.headers)
    parser.register('my_attachment', ffile)

    async for chunk in request.stream():
        parser.data_received(chunk)

    print('--------------------')
    print(ffile.value)

    return {'example': 123}

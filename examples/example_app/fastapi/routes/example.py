import asyncio

from fastapi import APIRouter, Path, Query, Depends
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

from frontik.fastapi_integration import FrontikFastApiRoute
from frontik.handler import PageHandler

app_router = APIRouter(
    prefix="/test_fast_api", route_class=FrontikFastApiRoute, dependencies=[]
)


class StatusResponse(BaseModel):
    status: str
    query: int





@app_router.get("/{path_param}/test1", response_model=StatusResponse)
async def get_current_account(
    path_param: str = Path(), query_param: int = Query(), handler: PageHandler = Depends()
) -> StatusResponse:
    handler.get_url("localhost:9400", "/test_fast_api/test2?query_param=123")
    await asyncio.sleep(1)
    return StatusResponse(status=path_param, query=query_param)


@app_router.get("/test2")
async def get_current_account(request: Request, query_param: int = Query()):
    return JSONResponse(content={"param": query_param})

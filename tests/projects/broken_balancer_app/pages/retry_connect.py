from fastapi import HTTPException

from frontik.handler import PageHandler
from frontik.routing import router


@router.post('/retry_connect', cls=PageHandler)
async def post_page():
    raise HTTPException(503, 'broken, retry')

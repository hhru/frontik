from fastapi import HTTPException

from frontik.handler import PageHandler
from frontik.routing import router


@router.post('/no_retry_error', cls=PageHandler)
async def post_page():
    raise HTTPException(500, 'something went wrong, no retry')

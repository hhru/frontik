from fastapi import HTTPException

from frontik.handler import PageHandler
from frontik.routing import router


@router.put('/profile_without_retry', cls=PageHandler)
async def put_page():
    raise HTTPException(503, 'broken')

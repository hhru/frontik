from fastapi import HTTPException

from frontik.handler import PageHandler
from frontik.routing import router


@router.post('/retry_non_idempotent_503', cls=PageHandler)
async def post_page():
    raise HTTPException(503, 'broken, retry')

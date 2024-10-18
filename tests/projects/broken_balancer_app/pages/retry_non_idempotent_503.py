from fastapi import HTTPException

from frontik.routing import router


@router.post('/retry_non_idempotent_503')
async def post_page():
    raise HTTPException(503, 'broken, retry')

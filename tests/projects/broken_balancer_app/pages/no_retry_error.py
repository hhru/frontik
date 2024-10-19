from fastapi import HTTPException

from frontik.routing import router


@router.post('/no_retry_error')
async def post_page():
    raise HTTPException(500, 'something went wrong, no retry')

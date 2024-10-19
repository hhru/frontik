from fastapi import HTTPException

from frontik.routing import router


@router.put('/retry_error')
async def put_page():
    raise HTTPException(503, 'broken, retry')

from fastapi import HTTPException

from frontik.routing import router


@router.put('/profile_with_retry')
async def put_page():
    raise HTTPException(503, 'broken')

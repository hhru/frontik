from fastapi import Request

from frontik.routing import router


@router.get('/call_registration_stat')
async def get_page(request: Request) -> dict:
    return request.app.registration_call_counter

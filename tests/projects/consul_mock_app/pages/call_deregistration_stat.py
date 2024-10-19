from fastapi import Request

from frontik.routing import router


@router.get('/call_deregistration_stat')
async def get_page(request: Request) -> dict:
    return request.app.deregistration_call_counter

from fastapi import APIRouter

from frontik.dependencies import http_client

router = APIRouter()


@router.get('/example')
async def example_page() -> dict:
    result = await http_client.get_url('http://example.com', '/')
    return {'example': result.status_code}

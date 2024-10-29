from fastapi import APIRouter

from frontik.dependencies import HttpClient

router = APIRouter()


@router.get('/example')
async def example_page(http_client: HttpClient) -> dict:
    result = await http_client.get_url('http://example.com', '/')
    return {'example': result.status_code}

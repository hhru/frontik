from frontik.dependencies import HttpClient
from frontik.routing import router


@router.get('/example')
async def example_page(http_client: HttpClient) -> dict:
    result = await http_client.get_url('http://example.com', '/')
    return {'example': result.status_code}

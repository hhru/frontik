from fastapi import Response

from frontik.dependencies import HttpClientT
from frontik.routing import router


@router.get('/http_client/proxy_code')
async def get_page(port: str, http_client: HttpClientT):
    result = await http_client.get_url('http://127.0.0.1:' + port, '')
    return Response(str(result.status_code))

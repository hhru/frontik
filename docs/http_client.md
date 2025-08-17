## HttpClient

В проекте используется https://forgejo.pyn.ru/hhru/balancing-http-client.
Внутри это aiohttp с дополнительной логикой ретраев/балансировки.
Фронтик приложение создает один экземпляр на старте.
В качестве апстримов передается обновляемый список, получаемый из консула

### Пример использования

```python
from frontik.dependencies import HttpClient
from frontik.routing import router

@router.get('/my_page')
async def my_page(http_client: HttpClient) -> None:
    result = await http_client.get_url('google.com', '/')
```

### Отправить несколько запросов параллельно

```python
import asyncio
from frontik.dependencies import HttpClient
from frontik.routing import router

@router.get('/my_page')
async def my_page(http_client: HttpClient) -> None:
    res1, res2 = await asyncio.gather(http_client.get_url('google.com', '/'), http_client.get_url('google.com', '/'))
```

### Получить типизированный ответ

```python
import asyncio
from frontik.dependencies import HttpClient
from frontik.routing import router
from http_client.request_response import RequestResult


class MyDto(BaseModel):
    name: str | None
    numbers: list[int]


@router.get('/my_page')
async def my_page(http_client: HttpClient) -> MyDto:
    request_result: RequestResult[MyDto] = await http_client.get_url(
        'server_host',
        '/some_data',
    )
    request_data: MyDto = request_result.parse(MyDto)
    request_data.name = 'qqq'
    return request_data
```

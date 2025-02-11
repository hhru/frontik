## HttpClient

В проекте используется https://forgejo.pyn.ru/hhru/balancing-http-client.
Внутри это aiohttp с дополнительной логикой ретраев/балансировки.
Фронтик приложение создает один экземпляр на старте.
В качестве апстримов передается обновляемый список, получаемый из консула

Пример использования

```python
from frontik.dependencies import HttpClient
from frontik.routing import router

@router.get('/my_page')
async def my_page(http_client: HttpClient) -> None:
    result = await http_client.get_url('google.com', '/')
```

Как отправить несколько запросов параллельно

```python
import asyncio
from frontik.dependencies import HttpClient
from frontik.routing import router

@router.get('/my_page')
async def my_page(http_client: HttpClient) -> None:
    res1, res2 = await asyncio.gather(http_client.get_url('google.com', '/'), http_client.get_url('google.com', '/'))
```

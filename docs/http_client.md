## HttpClient

В проекте используется https://forgejo.pyn.ru/hhru/balancing-http-client.
Внутри это aiohttp с дополнительной логикой ретраев/балансировки.
Фронтик сам конструирует экземпляр клиента под каждый запрос.
В качестве апстримов передается обновляемый список, получаемый из консула

Пример использования

```python
from frontik.dependencies import http_client
from frontik.routing import router

@router.get('/my_page')
async def my_page() -> None:
    result = await http_client.get_url('google.com', '/')
```

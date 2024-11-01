## Routing

Конечные сервисы должны использовать [роутинг из fastapi](https://fastapi.tiangolo.com/tutorial/bigger-applications/).

Дефолтный роутер доступен по ссылке `frontik.routing.router`
```python
from frontik.routing import router

@router.get('/my_page')
async def my_page() -> str:
    return 'Hello World'
```

На старте приложения происходит импорт всех *.py файлов из модуля pages (см [Рекомендуемая структура проекта](README.md)).
Следует размещать контроллеры там.

Если необходимо создать свой роутер, то нужно использовать `frontik.routing.FastAPIRouter` (вместо `fastapi.APIRouter`).
Т.к. он автоматически подключается в приложение

Для поддержки старого кода временно существет `frontik.routing.regex_router` в который можно передавать произвольный регекспы.
В следующих версиях он будет удален

Дефолтные контроллеры фронтик приложения
* `/status` – возвращает `200 OK` если сервер готов принимать запросы. Ответ содержит json с дополнительной информацией
```json
{
    "uptime": "99.28 hours and 16.53 minutes"
}
```
* `/version` – xml с версией приложения и некоторых зависимостей

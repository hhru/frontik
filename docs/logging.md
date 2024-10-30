## Logging

На старте приложения фронтик выставляет уровень NOTSET для `logging.root`,
а так же инициализирует несколько базовых логеров (`server`, `service`, `requests`) методом `frontik.logging.bootstrap_logger`.
`service` является рутовым логгером, без доп настроек любые новые логгеры будут попадать в его хендлеры.

`bootstrap_logger` выставляет логгерам propagate = False, а также добавляет хендлеры логерам в зависимости от настроек.
доступные хендлеры - syslog, file, stderr, debug (добавляется всегда, нужен для дебаг страницы).
Настройка `options.log_level` проставляется в хендлеры, не в логеры.

Как написать что-нибудь в лог
```python
import logging
from frontik.routing import router

logger = logging.getLogger('handler')

@router.get('/my_page')
async def my_page() -> None:
    logger.info('start my_page')
```

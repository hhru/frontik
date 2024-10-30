## Frontik

Frontik это питон вебсервер + фреймворк 

Ранее (версии 7.* и ниже) был оберткой над [tornado](https://www.tornadoweb.org/). 
С версии 8.* идет работа над превращением фронтика в [asgi](https://asgi.readthedocs.io/) сервер. 
Конечные сервисы должны стремиться использовать asgi фреймворк (fastapi).
В 8.* все еще является вебсервером + фреймворком.

#### Рекомендуемая структура проекта
```
project_name/
    ├── service_name/
        ├── pages/       - контроллеры
        ├── __init__.py  - класс приложения, наследующий frontik.app.FrontikApplication
        └── version.py
    ├── tests/
    └── pyproject.toml
```

#### Установка

```shell
pip install 'frontik@git+ssh://git@github.com/hhru/frontik'
```

#### Запуск из кода

```python
from frontik.server import main

if __name__ == '__main__':
    main('./frontik.cfg')
```

#### Запуск из командной строки

```shell
/usr/bin/frontik --config=/path/to/frontik.cfg
```

Подробнее про настройки можно прочитать [здесь](configs.md).

#### Пример приложения

[example_app](/examples)

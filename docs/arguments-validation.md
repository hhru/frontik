## Argument validation

For fastapi routing see fastapi docs

- Query - https://fastapi.tiangolo.com/tutorial/query-params-str-validations/
- Body - https://fastapi.tiangolo.com/tutorial/body-fields/
- Body - https://fastapi.tiangolo.com/tutorial/body-nested-models/
- Path - https://fastapi.tiangolo.com/tutorial/path-params/

In legacy controllers, path params don't work as fastapi. You need to use regex router and then get params with `get_path_argument`:

Path param example:

```python
from frontik.routing import regex_router
from frontik.handler import PageHandler, get_current_handler

@regex_router.get(r'^/city/(?P<city_name>[\w\-\']+)', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    result = handler.get_path_argument('city_name')
    ...
```

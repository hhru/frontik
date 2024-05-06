## Argument validation

Use methods described in

- Query - https://fastapi.tiangolo.com/tutorial/query-params-str-validations/
- Body - https://fastapi.tiangolo.com/tutorial/body-fields/
- Body - https://fastapi.tiangolo.com/tutorial/body-nested-models/

Unlike other params, path params don't work as https://fastapi.tiangolo.com/tutorial/path-params/
because right now there is no way to set parametric url. Temporarily you can use regex router as a workaround.
We are going to migrate on fastapi native routing soon, so don't use very complicated regex

Path param example:

```python
from frontik.routing import regex_router
from frontik.handler import PageHandler, get_current_handler

@regex_router.get(r'^/city/(?P<city_name>[\w\-\']+)', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    result = handler.get_path_argument('city_name')
    ...
```

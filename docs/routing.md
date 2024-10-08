## Routing in Frontik applications

On application start, frontik import all modules from {app_module}.pages so that any controller should be located there.
We use fastapi routing, read [these docs](https://fastapi.tiangolo.com/reference/apirouter/?h=apirouter) for details.

> [!IMPORTANT]
> Never inherit from the `fastapi.APIRouter` router directly, instead you should use wrapped alternative from [`frontik.routing.FastAPIRouter`](https://github.com/hhru/frontik/blob/526a4cc22d151694fa48439f884dd03a6ca2329f/frontik/routing.py#L110)
>
> If you won't customize router behaviour then simply import `from frontik.routing import router`

example:

```python
from frontik.routing import router

@router.get("/users/me")
async def read_user_me():
    return {"username": "fakecurrentuser"}

```

### Deprecated

Page generation logic with (pre/post)processors and finish group from previous versions is temporarily supported. You need to add `cls=PageHandler` arg to route:

```python
from frontik.routing import plain_router
from frontik.handler import PageHandler


@plain_router.get('/simple_page', cls=PageHandler)  # or .post .put .delete .head
async def get_page():
    ...
```

If you need regex with path params use `from frontik.routing import regex_router`. The handler object can be accessed via `request.state.handler`
You can use fastapi dependencies functions in router, see https://fastapi.tiangolo.com/tutorial/dependencies/ and https://fastapi.tiangolo.com/tutorial/bigger-applications/#another-module-with-apirouter for details

Example with dependencies:

```python
from frontik.routing import plain_router
from frontik.handler import PageHandler, get_current_handler
from fastapi import Depends


@plain_router.get('/simple_page', cls=PageHandler, dependencies=[Depends(my_foo)])
async def get_page(handler=get_current_handler()):
    ...
```

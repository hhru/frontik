## Dependency injection

We are in the process of migrating to fastapi. But, we still use the server and routing from tornado. 
So, in order to specify dependencies for handler, you should pass dependencies to router decorator.
There is special dependency `get_current_handler` for getting PageHandler object

```python
from frontik.dependency_manager import APIRouter
from fastapi import Depends
from frontik.handler import PageHandler, get_current_handler

router = APIRouter(dependencies=[Depends(some_dependency_function)])


async def get_session_dependency(handler: PageHandler = Depends(get_current_handler)):
    token = handler.get_cookie('token')
    await session_client.get_session(token)


class Page(PageHandler):
    @router.get(dependencies=[Depends(get_session_dependency)])
    async def get_page(self):
        ...
```

If you don’t need to use special dependencies at the router level, then you can use router from the frontik.handler
```py
from frontik.handler import router
```

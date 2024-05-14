## Routing in Frontik applications

On application start, frontik import all modules from {app_module}.pages so that any controller should be located there.

Controller example:
```python
from frontik.routing import router
from frontik.handler import PageHandler

@router.get('/simple_page', cls=PageHandler)  # or .post .put .delete .head
async def get_page():
    ...
```

First argument path should be exact string for url matching. 
If you need regex with path params use `from frontik.routing import regex_router`

Argument `cls=PageHandler` is required for legacy compatibility, it defines which class will be used to create the handler object.
The handler object can be accessed via `request.state.handler`

You can use 'dependencies' functions in router or method arguments, see https://fastapi.tiangolo.com/tutorial/dependencies/ and https://fastapi.tiangolo.com/tutorial/bigger-applications/#another-module-with-apirouter for details

Example with dependencies:
```python
from frontik.routing import router
from frontik.handler import PageHandler, get_current_handler
from fastapi import Depends

@router.get('/simple_page', cls=PageHandler, dependencies=[Depends(my_foo)])
async def get_page(handler=get_current_handler()):
    ...
```

You can create your own router object by extending `frontik.routing.FrontikRouter` and `frontik.routing.FrontikRegexRouter`

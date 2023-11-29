## Dependency injection

Dependency injection is a pattern when a function receives other functions that it requires, 
instead of creating them internally. 
In frontik implementation, dependencies are simple functions, 
which run after `RequestHandler.prepare` and before* handler code is executed.
Dependencies are great for running common actions before actual request processing takes place.

Here is what a dependencies may look like:

```python
from frontik.dependency_manager import dependency


async def get_session_dependency(handler: PageHandler) -> Session:
    token = handler.get_cookie('token')
    return await session_client.get_session(token)


class Page(PageHandler):
    # Can be used on class level
    dependencies = (another_dependency,)

    async def get_page(self, session=dependency(get_session_dependency)):
        self.json.put({'result': session})
```

If you have several dependencies without results, you can put them all to one dependency marker
```python
from frontik.dependency_manager import dependency


async def check_host(handler: PageHandler) -> None:
    if handler.request.host != 'example':
        raise HttpError()

    
async def check_session(session=dependency(get_session_dependency)) -> None:
    if session.role != 'admin':
        raise HttpError()


class Page(PageHandler):
    async def get_page(self, _=dependency(check_host, check_session)):
        ...
```

Dependency can be sync or async functions. When page is executed all ready to run 
async dependencies run in parallel with asyncio.gather(). If something finishes the page 
(call self.finish() or raise Exception), then we stop executing the remaining dependencies

Dependencies can depend on another dependencies, thus we have a dependency graph. 
Within one execution of a graph, the same dependencies will be executed once.
Sameness is determined by {function.__module__}.{function.__name__}
Dependencies can come from factories, then it turns out that there are several different dependencies
with the same name. In this case the one that is specified explicitly in the method arg or 
in class level will be taken, the rest from the graph depths will be discarded


There is an opportunity to specify priorities for dependencies:

```python
from frontik.dependency_manager import dependency


async def get_session_dependency(handler: PageHandler) -> Session:
    token = handler.get_cookie('token')
    return await session_client.get_session(token)


class Page(PageHandler):
    # Can be used on class level
    dependencies = (another_dependency,)
    _priority_dependency_names: list[str] = [
        side_dependency,
        another_dependency,
    ]

    async def get_page(self, session=dependency(get_session_dependency)):
        self.json.put({'result': session})
```
If any of the _priority_dependency_names are present in the current graph, 
they will be executed before all the other dependencies sequentially. 
In the given example `another_dependency` -> `get_session_dependency` -> `get_page`


*It is also possible to specify "async" dependencies:

```python
from frontik.dependency_manager import dependency, async_dependencies


async def get_session_dependency(handler: PageHandler) -> Session:
    token = handler.get_cookie('token')
    return await session_client.get_session(token)


class Page(PageHandler):
    @async_dependencies([get_session_dependency])
    async def get_page(self):
        self.json.put({'result': 'done'})
```
The passed list will not block the execution of the page_method, so they can be executed in parallel


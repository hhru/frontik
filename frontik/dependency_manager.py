from typing import Any, Callable

from fastapi import APIRouter as FastApiRouter
from fastapi import Request
from fastapi.dependencies.utils import solve_dependencies


class APIRouter(FastApiRouter):
    def get(self, **kwargs) -> Callable:  # type: ignore
        return super().get('', **kwargs)

    def post(self, **kwargs) -> Callable:  # type: ignore
        return super().post('', **kwargs)

    def put(self, **kwargs) -> Callable:  # type: ignore
        return super().put('', **kwargs)

    def delete(self, **kwargs) -> Callable:  # type: ignore
        return super().delete('', **kwargs)

    def api_route(self, *args, **kwargs):
        decorator = super().api_route(*args, **kwargs)

        def frontik_decorator(func):
            decorator(func)
            func._route = self.routes[-1]
            route_method = func._route.methods  # type: ignore

            if func.__name__ in ('get_page', 'post_page', 'put_page', 'delete_page') and route_method != {
                func.__name__.split('_')[0].upper(),
            }:
                raise RuntimeError(f'Wrong router type func={func.__name__} method={route_method}')
            return func

        return frontik_decorator


async def execute_page_method_with_dependencies(handler: Any, get_page_method: Callable) -> Any:
    request = Request({
        'type': 'http',
        'query_string': '',
        'headers': '',
        'handler': handler,
    })

    route = get_page_method._route  # type: ignore

    await solve_dependencies(request=request, dependant=route.dependant, body=None, dependency_overrides_provider=None)

    return await get_page_method()

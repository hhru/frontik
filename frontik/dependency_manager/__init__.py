from __future__ import annotations

from typing import TYPE_CHECKING, Any

from frontik.dependency_manager.dependencies import DependencyGroupMarker, DependencyMarker
from frontik.dependency_manager.graph_builder import build_sub_graph, get_dependency_graph
from frontik.dependency_manager.graph_runner import execute_graph
from frontik.preprocessors import Preprocessor, make_full_name

if TYPE_CHECKING:
    from collections.abc import Callable

    from frontik.handler import PageHandler
    from frontik.handler_return_values import ReturnedValue


def dependency(*deps: Preprocessor | Callable) -> Any:
    """
    add dependency to page_method, it will be run before page_method and provide result

    async def get_page(self, session=dependency(get_session)):
      ...
    """
    if len(deps) == 1:
        dep = deps[0]

        if isinstance(dep, Preprocessor):
            return DependencyMarker(dep.preprocessor_function)

        if callable(dep):
            return DependencyMarker(dep)

        raise ValueError('Bad dependency type, only func or list[func]')

    else:
        return DependencyGroupMarker(tuple(deps))


def async_dependencies(async_deps: list[Callable]) -> Callable:
    """
    add dependencies that will be run in parallel with page_method

    @async_dependencies([get_session, get_data])
    async def get_page(self):
      ...
    """

    def decorator(execute_page_method: Callable) -> Callable:
        setattr(execute_page_method, '_async_deps', async_deps)
        return execute_page_method

    return decorator


async def build_and_run_sub_graph(handler: PageHandler, functions_to_run: list) -> None:
    sub_graph = build_sub_graph(handler, functions_to_run)
    await execute_graph(handler, sub_graph)


async def execute_page_method_with_dependencies(handler: PageHandler, page_method: Any) -> ReturnedValue:
    main_graph = get_dependency_graph(page_method.__func__, handler.__class__)
    setattr(handler, '_main_graph', main_graph)
    await execute_graph(handler, main_graph)
    return main_graph.root_dep.result


def make_dependencies_names_list(dependencies_list: list) -> list[str]:
    return [make_full_name(d) for d in dependencies_list]

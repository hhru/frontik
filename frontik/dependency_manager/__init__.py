from __future__ import annotations

from typing import TYPE_CHECKING, Any

from frontik.dependency_manager.dependencies import DependencyMarker
from frontik.dependency_manager.graph_builder import build_sub_graph, get_dependency_graph
from frontik.dependency_manager.graph_runner import execute_graph
from frontik.preprocessors import DependencyGroupMarker, Preprocessor

if TYPE_CHECKING:
    from collections.abc import Callable

    from frontik.handler import PageHandler


def dep(dependency: Preprocessor | Callable | list[Callable]) -> Any:
    """
    add dependency to page_method, it will be run before page_method and provide result

    async def get_page(self, session=dep(get_session)):
      ...
    """
    if isinstance(dependency, Preprocessor) and not isinstance(dependency.preprocessor_function, DependencyGroupMarker):
        return DependencyMarker(dependency.preprocessor_function)

    if isinstance(dependency, list):
        return DependencyGroupMarker(dependency)

    if callable(dependency):
        return DependencyMarker(dependency)

    msg = 'Bad dependency type, only func or list[func]'
    raise ValueError(msg)


def async_deps(async_dependencies: list[Callable]) -> Callable:
    """
    add dependencies that will be run in parallel with page_method

    @async_dep([get_session, get_data])
    async def get_page(self):
      ...
    """

    def decorator(execute_page_method: Callable) -> Callable:
        setattr(execute_page_method, '_async_deps', async_dependencies)
        return execute_page_method

    return decorator


async def build_and_run_sub_graph(handler: PageHandler, functions_to_run: list) -> None:
    sub_graph = build_sub_graph(handler, functions_to_run)
    await execute_graph(handler, sub_graph)


async def execute_page_method_with_dependencies(handler: PageHandler, page_method: Any) -> Any:
    main_graph = get_dependency_graph(page_method.__func__, handler.__class__)
    setattr(handler, '_main_graph', main_graph)
    await execute_graph(handler, main_graph)
    return main_graph.root_dep.result

from __future__ import annotations

import asyncio
from graphlib import TopologicalSorter
from typing import TYPE_CHECKING, Optional

from frontik.preprocessors import make_full_name

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from frontik.handler import PageHandler


class DependencyMarker:
    def __init__(self, func: Callable) -> None:
        self.func = func


class DependencyGroupMarker:
    __name__ = 'dep_group'

    def __init__(self, deps: Iterable[Callable]) -> None:
        self.deps = deps


class Dependency:
    def __init__(self, func: Callable) -> None:
        self.func = func
        self.args: list = []
        self.result = None
        self.finished = False
        self.task: Optional[asyncio.Task] = None
        self.waited = True

    async def run(self) -> None:
        """
        replace self.args with the result of completed sub_dependencies and run self.func
        if sub_dependency is not finished raise RuntimeError
        """
        if self.finished:
            return

        for i, arg in enumerate(self.args):
            if isinstance(arg, Dependency):
                if not arg.finished:
                    raise RuntimeError(f'Graph corrupted, run {self}, before finishing {arg}')
                self.args[i] = arg.result

        if asyncio.iscoroutinefunction(self.func):
            if self.waited:
                self.result = await self.func(*self.args)
            else:
                asyncio.create_task(self.func(*self.args))
        else:
            self.result = self.func(*self.args)
        self.finished = True

    def __repr__(self):
        return make_full_name(self.func)


class DependencyGraph:
    """
    known_deps - to prevent re-registration of function multiple times
    registered_deps - to make correct dependency_links in case of building a sub_graph
    dependency_links - links dict for build TopologicalSorter
    handler_cls - special argument type for using special dependencies for example get_handler()
    """

    def __init__(self, root_dep: Dependency, handler_cls: type) -> None:
        self.root_dep: Dependency = root_dep
        self.known_deps: dict[str, Dependency] = {}
        self.registered_deps: set[Dependency] = set()
        self.dependency_links: dict[Dependency, set[Dependency]] = {root_dep: set()}
        self.handler_cls: type = handler_cls
        self.topological_sorter: Optional[TopologicalSorter[Dependency]] = None
        self.special_deps: set[Dependency] = set()

    def build_topological_sorter(self) -> None:
        self.topological_sorter = TopologicalSorter(self.dependency_links)
        self.topological_sorter.prepare()

    async def run_dependency(self, dependency: Dependency) -> None:
        await dependency.run()
        if self.topological_sorter is None:
            raise RuntimeError('There is no topological_sorter in dependency graph')
        self.topological_sorter.done(dependency)


def make_stub_dependency() -> Dependency:
    def stub():
        pass

    dependency = Dependency(stub)
    dependency.finished = True
    return dependency


def get_handler(handler: PageHandler) -> PageHandler:
    return handler

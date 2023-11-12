from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frontik.dependency_manager.dependencies import Dependency, DependencyGraph
    from frontik.handler import PageHandler


async def run_special_dependencies(handler: PageHandler, graph: DependencyGraph) -> None:
    for dependency in graph.special_deps:
        dependency.result = dependency.func(handler)
        dependency.finished = True


async def execute_graph(handler: PageHandler, graph: DependencyGraph) -> None:
    await run_special_dependencies(handler, graph)

    pending_tasks: set[asyncio.Task] = set()
    topological_sorter = graph.topological_sorter
    if topological_sorter is None:
        raise RuntimeError('There is no topological_sorter in dependency graph')

    while topological_sorter.is_active():
        dependencies_to_run: tuple[Dependency, ...] = topological_sorter.get_ready()

        if handler.is_finished():
            for p in pending_tasks:
                p.cancel()
            return

        for dependency in dependencies_to_run:
            task = asyncio.create_task(graph.run_dependency(dependency))
            pending_tasks.add(task)

        if pending_tasks:
            done, pending = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                if d.exception() is not None:
                    raise d.exception()  # type: ignore
                pending_tasks.remove(d)
            for p in pending:
                pending_tasks.add(p)

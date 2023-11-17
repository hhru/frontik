from __future__ import annotations

import inspect
from copy import copy, deepcopy
from itertools import chain
from typing import TYPE_CHECKING, Any

from frontik.dependency_manager.dependencies import (
    Dependency,
    DependencyGraph,
    DependencyMarker,
    get_handler,
    make_stub_dependency,
)
from frontik.preprocessors import (
    DependencyGroupMarker,
    Preprocessor,
    get_all_preprocessors_functions,
    get_simple_preprocessors_functions,
    make_full_name,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable

    from frontik.handler import PageHandler


def build_sub_graph(handler: PageHandler, dependencies_to_run: list) -> DependencyGraph:
    """
    building sub_graph
    duplicated dependencies will be taken from main graph
    """
    root_dep = make_stub_dependency()
    sub_graph = DependencyGraph(root_dep, handler.__class__)

    main_graph: DependencyGraph = getattr(handler, '_main_graph')
    sub_graph.known_deps = main_graph.known_deps

    # collect dependencies which defined explicitly
    shallow_dependencies = _get_shallow_functions(dependencies_to_run)
    _register_side_dependencies(sub_graph, root_dep, shallow_dependencies, deep_scan=False)

    # collect all dependencies with deep_scan
    all_dependencies = _get_all_functions(dependencies_to_run)
    _register_side_dependencies(sub_graph, root_dep, all_dependencies, deep_scan=True)

    _set_priority_links(handler.__class__._priority_dependency_names, sub_graph)
    sub_graph.build_topological_sorter()
    return sub_graph


def _get_shallow_functions(dependencies_to_run: list) -> Generator:
    for dependency_item in dependencies_to_run:
        if not isinstance(dependency_item, DependencyGroupMarker):
            yield dependency_item


def _get_all_functions(dependencies_to_run: list) -> Generator:
    for dependency_item in dependencies_to_run:
        if isinstance(dependency_item, DependencyGroupMarker):
            yield from dependency_item.deps
        else:
            yield dependency_item


def get_dependency_graph(page_method_func: Callable, handler_cls: type) -> DependencyGraph:
    """
    build meta_graph or make deepcopy as main_graph if meta_graph existed

    register dependencies from page_method_func args
    register legacy preprocessors and class level dependencies
    add extra links for handler priority_list
    """
    if hasattr(page_method_func, '_meta_graph'):
        return deepcopy(page_method_func._meta_graph)

    root_dep = Dependency(page_method_func)
    meta_graph = DependencyGraph(root_dep, handler_cls)

    handler_dependencies = getattr(handler_cls, 'dependencies', [])
    simple_preprocessors = chain(get_simple_preprocessors_functions(page_method_func), handler_dependencies)
    all_preprocessors = chain(get_all_preprocessors_functions(page_method_func), handler_dependencies)

    # collect dependencies which defined explicitly
    _register_dependency_params(meta_graph, root_dep, add_to_args=False, deep_scan=False)
    _register_side_dependencies(meta_graph, root_dep, simple_preprocessors, deep_scan=False)

    # collect all dependencies with deep_scan
    _register_dependency_params(meta_graph, root_dep, add_to_args=True, deep_scan=True)
    _register_side_dependencies(meta_graph, root_dep, all_preprocessors, deep_scan=True)

    async_dependencies = getattr(page_method_func, '_async_deps', [])
    _register_async_dependencies(meta_graph, async_dependencies)

    priorities = getattr(handler_cls, '_priority_dependency_names', [])
    _set_priority_links(priorities, meta_graph)

    meta_graph.build_topological_sorter()
    setattr(page_method_func, '_meta_graph', meta_graph)
    return deepcopy(meta_graph)


def _register_side_dependencies(
    graph: DependencyGraph,
    root_dep: Dependency,
    side_dependencies: Iterable,
    deep_scan: bool,
) -> None:
    for function_or_preprocessor in side_dependencies:
        dependency = _make_dependency_for_graph(graph, function_or_preprocessor, deep_scan=deep_scan)
        if deep_scan:
            _register_sub_dependency(graph, root_dep, dependency, add_to_args=False)


def _register_async_dependencies(graph: DependencyGraph, async_dependencies: Iterable) -> None:
    root_dep = make_stub_dependency()
    for dependency_function in async_dependencies:
        dependency = _make_dependency_for_graph(graph, dependency_function, deep_scan=True)
        dependency.waited = False
        _register_sub_dependency(graph, root_dep, dependency, add_to_args=False)


def _set_priority_links(priority_list: list[str], graph: DependencyGraph) -> None:
    """
    add extra links for handler priority_list

    filter priority_list against registered dependencies
    link each with each in a chain
    link remaining registered dependencies on last one from priority_list
    """
    priority_filtered: list[Dependency] = []
    for func_name in priority_list:
        if func_name not in graph.known_deps:
            continue
        priority_dep = graph.known_deps[func_name]
        if priority_dep in graph.registered_deps and priority_dep not in priority_filtered:
            priority_filtered.append(priority_dep)

    if len(priority_filtered) > 1:
        for i in range(len(priority_filtered) - 1):
            cur_dep = priority_filtered[i]
            next_dep = priority_filtered[i + 1]

            if next_dep not in graph.dependency_links:
                graph.dependency_links[next_dep] = {cur_dep}
                continue

            if cur_dep not in graph.dependency_links[next_dep]:
                graph.dependency_links[next_dep].add(cur_dep)

    if len(priority_filtered) > 0:
        last_priority_dep = priority_filtered[-1]
        should_depends_on_last = copy(graph.registered_deps)

        for d in priority_filtered:
            should_depends_on_last.discard(d)
            for sd in graph.dependency_links.get(d, set()):
                should_depends_on_last.discard(sd)

        for d in should_depends_on_last:
            if d not in graph.dependency_links:
                graph.dependency_links[d] = {last_priority_dep}
            elif last_priority_dep not in graph.dependency_links[d]:
                graph.dependency_links[d].add(last_priority_dep)


def _register_dependency_params(
    graph: DependencyGraph,
    dependency: Dependency,
    add_to_args: bool,
    deep_scan: bool,
) -> None:
    signature_params = inspect.signature(dependency.func).parameters

    for param_name, param in signature_params.items():
        if isinstance(param.default, DependencyMarker):
            sub_dependency = _make_dependency_for_graph(graph, param.default.func, deep_scan)
            if deep_scan:
                _register_sub_dependency(graph, dependency, sub_dependency, add_to_args)
            continue

        elif issubclass(graph.handler_cls, param.annotation):
            sub_dependency = _make_dependency_for_graph(graph, get_handler, deep_scan)
            graph.special_deps.add(sub_dependency)
            if deep_scan:
                _register_sub_dependency(graph, dependency, sub_dependency, add_to_args)
            continue

        elif param_name == 'self':
            sub_dependency = _make_dependency_for_graph(graph, get_handler, deep_scan)
            graph.special_deps.add(sub_dependency)
            if deep_scan:
                _register_sub_dependency(graph, dependency, sub_dependency, add_to_args)

        else:
            raise ValueError(f'Only dependencies or handler could be in params, dep:{dependency} param:{param}')


def _register_sub_dependency(
    graph: DependencyGraph,
    dependency: Dependency,
    sub_dependency: Dependency,
    add_to_args: bool,
) -> None:
    """
    register sub dependency
    add to parent dependency args (if it was in signature)
    add link to graph
    deep scan sub_dependency parameters
    """
    if sub_dependency not in graph.registered_deps:
        graph.registered_deps.add(sub_dependency)
        need_add_to_args = len(sub_dependency.args) == 0
        if sub_dependency not in graph.special_deps:
            _register_dependency_params(graph, sub_dependency, need_add_to_args, True)

    if add_to_args:
        dependency.args.append(sub_dependency)

    if dependency in graph.dependency_links:
        graph.dependency_links[dependency].add(sub_dependency)
    else:
        graph.dependency_links[dependency] = {sub_dependency}


def _make_dependency_for_graph(graph: DependencyGraph, function_or_preprocessor: Any, deep_scan: bool) -> Dependency:
    """
    make dependency from function
    if function is Preprocessor, then take underlying function
    duplicates would be avoided based on known_deps from graph

    if there are two different dependency with same name (factory's dependency), then leave only first
    if they both are in signature explicitly, raise ValueError('Dependency conflict')
    """
    if isinstance(function_or_preprocessor, Preprocessor):
        function_or_preprocessor = function_or_preprocessor.preprocessor_function

    function_name = make_full_name(function_or_preprocessor)

    if function_name in graph.known_deps:
        sub_dependency = graph.known_deps[function_name]

        if sub_dependency.func != function_or_preprocessor and not deep_scan:
            raise ValueError(f'Dependency conflict {sub_dependency.func} != {function_or_preprocessor}')

    else:
        sub_dependency = Dependency(function_or_preprocessor)
        graph.known_deps[function_name] = sub_dependency

    return sub_dependency

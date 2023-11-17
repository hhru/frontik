import asyncio
from collections.abc import Callable

import pytest

from frontik.dependency_manager import async_deps, build_and_run_sub_graph, dep, execute_page_method_with_dependencies
from frontik.handler import PageHandler


class TestPageHandler(PageHandler):
    _priority_dependency_names: list[str] = []
    x = '0'

    def __init__(self) -> None:
        self.finished = False

    def is_finished(self):
        return self.finished


DEP_LOG = []


async def get_session(handler: TestPageHandler) -> str:
    DEP_LOG.append('get_session')
    await asyncio.sleep(0.1)
    return 'session' + handler.x


def check_session(handler: TestPageHandler, _session: str = dep(get_session)) -> str:
    DEP_LOG.append('check_session')
    return 'check' + handler.x


async def get_some_data(handler: TestPageHandler) -> str:
    DEP_LOG.append('get_some_data')
    await asyncio.sleep(0.1)
    return 'data' + handler.x


def dep_factory(closure_param: int) -> Callable:
    def internal_dep() -> int:
        DEP_LOG.append(f'internal_dep_{closure_param}')
        return closure_param

    return internal_dep


def dep_group(data: int = dep(dep_factory(2)), _: str = dep(check_session), __: str = dep(get_some_data)) -> int:
    DEP_LOG.append('dep_group')
    return data


async def exception_dep() -> None:
    DEP_LOG.append('exception_dep')
    msg = 'stub_error'
    raise ArithmeticError(msg)


async def finisher_dep(handler: TestPageHandler) -> None:
    DEP_LOG.append('finisher_dep')
    handler.finished = True


async def dep_with_subgraph(handler: TestPageHandler) -> None:
    await build_and_run_sub_graph(handler, [finisher_dep])


class SimpleHandler(TestPageHandler):
    x = '1'

    async def get_page(self, session=dep(get_session), check=dep(check_session), data=dep(get_some_data)):
        DEP_LOG.append('get_page')
        return f'{session}_{check}_{data}'

    async def post_page(self, group=dep(dep_group), data=dep(dep_factory(1))):
        DEP_LOG.append('post_page')
        return f'{group}_{data}'

    async def put_page(self, data1=dep(dep_factory(1)), data2=dep(dep_factory(2))):
        DEP_LOG.append('put_page')
        return f'{data1}_{data2}'


class PriorityHandler(TestPageHandler):
    _priority_dependency_names: list[str] = [
        'tests.test_dependencies.internal_dep',
        'tests.test_dependencies.get_some_data',
        'tests.test_dependencies.finisher_dep',
    ]

    async def get_page(self, session=dep(get_session), check=dep(check_session), data=dep(get_some_data)):
        DEP_LOG.append('get_page')
        return f'{session}_{check}_{data}'

    async def post_page(self, _=dep(exception_dep)):
        pass

    async def put_page(self, group=dep(dep_group), data=dep(dep_factory(1)), _=dep(finisher_dep)):
        DEP_LOG.append('put_page')
        return f'{group}_{data}'


class SubGraphHandler(TestPageHandler):
    dependencies = [dep_factory(1)]
    _priority_dependency_names: list[str] = [
        'tests.test_dependencies.internal_dep',
        'tests.test_dependencies.get_some_data',
        'tests.test_dependencies.finisher_dep',
    ]

    async def get_page(self, data=dep(get_some_data)):
        await build_and_run_sub_graph(self, [check_session])
        return data

    async def post_page(self, data1=dep(dep_group), data2=dep(dep_with_subgraph)):
        return f'{data1}_{data2}'


class AsyncDependencyHandler(TestPageHandler):
    @async_deps([check_session])
    async def get_page(self):
        DEP_LOG.append('get_page')


class TestDependencies:
    @staticmethod
    def setup_method():
        DEP_LOG.clear()

    async def test_simple_dependencies(self):
        handler = SimpleHandler()
        res = await asyncio.wait_for(execute_page_method_with_dependencies(handler, handler.get_page), timeout=0.15)
        assert len(DEP_LOG) == 4
        assert DEP_LOG.index('check_session') > DEP_LOG.index('get_session')
        assert res == 'session1_check1_data1'

    async def test_dep_group(self):
        handler = SimpleHandler()
        res = await asyncio.wait_for(execute_page_method_with_dependencies(handler, handler.post_page), timeout=0.15)
        assert len(DEP_LOG) == 6
        assert DEP_LOG.index('check_session') > DEP_LOG.index('get_session')
        assert res == '1_1'

    async def test_dep_conflict(self):
        handler = SimpleHandler()
        with pytest.raises(ValueError, match=r'Dependency conflict .*'):
            await execute_page_method_with_dependencies(handler, handler.put_page)
        assert len(DEP_LOG) == 0

    async def test_deps_with_priority(self):
        handler = PriorityHandler()
        res = await execute_page_method_with_dependencies(handler, handler.get_page)
        assert len(DEP_LOG) == 4
        assert DEP_LOG[0] == 'get_some_data'
        assert 'internal_dep' not in DEP_LOG
        assert DEP_LOG.index('check_session') > DEP_LOG.index('get_session')
        assert res == 'session0_check0_data0'

    async def test_exception_in_dep(self):
        handler = PriorityHandler()
        with pytest.raises(ArithmeticError, match=r'stub_error'):
            await execute_page_method_with_dependencies(handler, handler.post_page)

    async def test_dep_with_finisher(self):
        handler = PriorityHandler()
        res = await execute_page_method_with_dependencies(handler, handler.put_page)
        assert len(DEP_LOG) == 3
        assert DEP_LOG[0] == 'internal_dep_1'
        assert DEP_LOG[1] == 'get_some_data'
        assert DEP_LOG[2] == 'finisher_dep'
        assert res is None

    async def test_subgraph_in_page(self):
        handler = SubGraphHandler()
        res = await execute_page_method_with_dependencies(handler, handler.get_page)
        assert ['internal_dep_1', 'get_some_data', 'get_session', 'check_session'] == DEP_LOG
        assert res == 'data0'

    async def test_subgraph_in_dep(self):
        handler = SubGraphHandler()
        res = await execute_page_method_with_dependencies(handler, handler.post_page)
        assert ['internal_dep_1', 'get_some_data', 'get_session', 'finisher_dep'] == DEP_LOG
        assert res is None

    async def test_async_deps(self):
        handler = AsyncDependencyHandler()
        await execute_page_method_with_dependencies(handler, handler.get_page)
        assert ['get_page', 'get_session', 'check_session'] == DEP_LOG

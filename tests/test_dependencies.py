import asyncio
from collections.abc import Callable

import pytest

from frontik.dependency_manager import (
    async_dependencies,
    build_and_run_sub_graph,
    dependency,
    execute_page_method_with_dependencies,
)
from frontik.handler import PageHandler


class BaseTestHandler(PageHandler):
    _priority_dependency_names: list[str] = []
    x = '0'

    def __init__(self) -> None:
        self.finished = False

    def is_finished(self):
        return self.finished


DEP_LOG = []


async def get_session(handler: BaseTestHandler) -> str:
    DEP_LOG.append('get_session')
    await asyncio.sleep(0.1)
    return 'session' + handler.x


def check_session(handler: BaseTestHandler, _session: str = dependency(get_session)) -> str:
    DEP_LOG.append('check_session')
    return 'check' + handler.x


async def get_some_data(handler: BaseTestHandler) -> str:
    DEP_LOG.append('get_some_data')
    await asyncio.sleep(0.1)
    return 'data' + handler.x


def dep_factory(closure_param: int) -> Callable:
    def internal_dep() -> int:
        DEP_LOG.append(f'internal_dep_{closure_param}')
        return closure_param

    return internal_dep


def dep_group(
    data: int = dependency(dep_factory(2)),
    _: str = dependency(check_session),
    __: str = dependency(get_some_data),
) -> int:
    DEP_LOG.append('dep_group')
    return data


async def exception_dep() -> None:
    DEP_LOG.append('exception_dep')
    msg = 'stub_error'
    raise ArithmeticError(msg)


async def finisher_dep(handler: BaseTestHandler) -> None:
    DEP_LOG.append('finisher_dep')
    handler.finished = True


async def dep_with_subgraph(handler: BaseTestHandler) -> None:
    await build_and_run_sub_graph(handler, [finisher_dep])


class SimpleHandler(BaseTestHandler):
    x = '1'

    async def get_page(
        self,
        session=dependency(get_session),
        check=dependency(check_session),
        data=dependency(get_some_data),
    ):
        DEP_LOG.append('get_page')
        return f'{session}_{check}_{data}'

    async def post_page(self, group=dependency(dep_group), data=dependency(dep_factory(1))):
        DEP_LOG.append('post_page')
        return f'{group}_{data}'

    async def put_page(self, data1=dependency(dep_factory(1)), data2=dependency(dep_factory(2))):
        DEP_LOG.append('put_page')
        return f'{data1}_{data2}'


class PriorityHandler(BaseTestHandler):
    _priority_dependency_names: list[str] = [
        'tests.test_dependencies.internal_dep',
        'tests.test_dependencies.get_some_data',
        'tests.test_dependencies.finisher_dep',
    ]

    async def get_page(
        self,
        session=dependency(get_session),
        check=dependency(check_session),
        data=dependency(get_some_data),
    ):
        DEP_LOG.append('get_page')
        return f'{session}_{check}_{data}'

    async def post_page(self, _=dependency(exception_dep)):
        pass

    async def put_page(self, group=dependency(dep_group), data=dependency(dep_factory(1)), _=dependency(finisher_dep)):
        DEP_LOG.append('put_page')
        return f'{group}_{data}'


class SubGraphHandler(BaseTestHandler):
    dependencies = [dep_factory(1)]
    _priority_dependency_names: list[str] = [
        'tests.test_dependencies.internal_dep',
        'tests.test_dependencies.get_some_data',
        'tests.test_dependencies.finisher_dep',
    ]

    async def get_page(self, data=dependency(get_some_data)):
        await build_and_run_sub_graph(self, [check_session])
        return data

    async def post_page(self, data1=dependency(dep_group), data2=dependency(dep_with_subgraph)):
        return f'{data1}_{data2}'


class AsyncDependencyHandler(BaseTestHandler):
    @async_dependencies([check_session])
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
        assert DEP_LOG == ['internal_dep_1', 'get_some_data', 'get_session', 'check_session']
        assert res == 'data0'

    async def test_subgraph_in_dep(self):
        handler = SubGraphHandler()
        res = await execute_page_method_with_dependencies(handler, handler.post_page)
        assert DEP_LOG == ['internal_dep_1', 'get_some_data', 'get_session', 'finisher_dep']
        assert res is None

    async def test_async_deps(self):
        handler = AsyncDependencyHandler()
        await execute_page_method_with_dependencies(handler, handler.get_page)
        assert DEP_LOG == ['get_page', 'get_session', 'check_session']

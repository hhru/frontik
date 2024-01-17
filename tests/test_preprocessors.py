import asyncio
from collections.abc import Callable

import pytest

from frontik.dependency_manager import build_and_run_sub_graph, dependency, execute_page_method_with_dependencies
from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor


class BaseTestHandler(PageHandler):
    _priority_dependency_names: list[str] = []
    x = '0'

    def __init__(self) -> None:
        self.finished = False

    def is_finished(self):
        return self.finished


DEP_LOG = []


@preprocessor
async def get_session(handler: BaseTestHandler) -> None:
    DEP_LOG.append('get_session')
    await asyncio.sleep(0.1)
    handler.session = 'session' + handler.x  # type: ignore


@preprocessor
def check_session(handler: BaseTestHandler, _session: None = dependency(get_session)) -> None:
    DEP_LOG.append('check_session')
    handler.check = 'check' + handler.x  # type: ignore


@preprocessor
async def get_some_data(handler: BaseTestHandler) -> None:
    DEP_LOG.append('get_some_data')
    await asyncio.sleep(0.1)
    handler.data = 'data' + handler.x  # type: ignore


def dep_factory(closure_param: int) -> Callable:
    @preprocessor
    def internal_dep(handler: BaseTestHandler) -> None:
        DEP_LOG.append(f'internal_dep_{closure_param}')
        handler.closure_param = closure_param  # type: ignore

    return internal_dep


def dep_group() -> Callable:
    def _dep_group(_=dependency(dep_factory(2), check_session, get_some_data)):
        DEP_LOG.append('dep_group')

    return preprocessor(_dep_group)


@preprocessor
async def exception_dep() -> None:
    DEP_LOG.append('exception_dep')
    msg = 'stub_error'
    raise ArithmeticError(msg)


@preprocessor
async def finisher_dep(handler: BaseTestHandler) -> None:
    DEP_LOG.append('finisher_dep')
    handler.finished = True


@preprocessor
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
        return f'{self.session}_{self.check}_{self.data}'  # type: ignore

    @dep_factory(1)
    @dep_group()
    async def post_page(self):
        DEP_LOG.append('post_page')
        return f'{self.session}_{self.check}_{self.data}'  # type: ignore

    @dep_factory(1)
    async def put_page(self, _data=dependency(dep_factory(2))):
        DEP_LOG.append('put_page')


class PriorityHandler(BaseTestHandler):
    _priority_dependency_names: list[str] = [
        'tests.test_preprocessors.internal_dep',
        'tests.test_preprocessors.get_some_data',
        'tests.test_preprocessors.finisher_dep',
    ]

    @get_session
    @check_session
    @get_some_data
    async def get_page(self):
        DEP_LOG.append('get_page')
        return f'{self.session}_{self.check}_{self.data}'  # type: ignore

    @exception_dep
    async def post_page(self):
        pass

    @dep_group()
    @dep_factory(1)
    async def put_page(self, _=dependency(finisher_dep)):
        DEP_LOG.append('put_page')
        return f'{self.data}'  # type: ignore


class SubGraphHandler(BaseTestHandler):
    dependencies = [dep_factory(1)]
    _priority_dependency_names: list[str] = [
        'tests.test_preprocessors.internal_dep',
        'tests.test_preprocessors.get_some_data',
        'tests.test_preprocessors.finisher_dep',
    ]

    async def get_page(self, data=dependency(get_some_data)):
        await build_and_run_sub_graph(self, [check_session])
        return data

    async def post_page(self, data1=dependency(dep_group), data2=dependency(dep_with_subgraph)):
        return f'{data1}_{data2}'


class TestPreprocessors:
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
        assert res == 'session1_check1_data1'

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
        assert DEP_LOG == ['internal_dep_1', 'get_some_data', 'finisher_dep']
        assert res is None

    async def test_subgraph_in_page(self):
        handler = SubGraphHandler()
        res = await execute_page_method_with_dependencies(handler, handler.get_page)
        assert ['internal_dep_1', 'get_some_data', 'get_session', 'check_session'] == DEP_LOG
        assert res is None

    async def test_subgraph_in_dep(self):
        handler = SubGraphHandler()
        res = await execute_page_method_with_dependencies(handler, handler.post_page)
        assert DEP_LOG == ['internal_dep_1', 'finisher_dep']
        assert res is None

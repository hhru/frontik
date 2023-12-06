from collections.abc import Iterator

import pytest


@pytest.fixture(scope='session', autouse=True)
def _teardown_module() -> Iterator[None]:
    yield

    # from tests.instances import (
    #     frontik_balancer_app,
    #     frontik_broken_balancer_app,
    #     frontik_broken_config_app,
    #     frontik_broken_init_async_app,
    #     frontik_consul_mock_app,
    #     frontik_no_debug_app,
    #     frontik_re_app,
    #     frontik_test_app,
    # )
    #
    # frontik_broken_config_app.stop()
    # frontik_broken_init_async_app.stop()
    # frontik_no_debug_app.stop()
    # frontik_re_app.stop()
    # frontik_test_app.stop()
    # frontik_balancer_app.stop()
    # frontik_broken_balancer_app.stop()
    # frontik_consul_mock_app.stop()


def pytest_addoption(parser):
    parser.addoption('--files_for_lint', action='store', default='')


@pytest.fixture(scope='session')
def files_for_lint(pytestconfig):
    return pytestconfig.getoption('files_for_lint')

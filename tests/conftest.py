import asyncio
from collections.abc import Iterator

import pytest

from frontik.loggers import bootstrap_core_logging
from frontik.options import options


@pytest.fixture(scope='session', autouse=True)
def _teardown_module() -> Iterator[None]:
    yield

    from tests.instances import (
        frontik_balancer_app,
        frontik_broken_balancer_app,
        frontik_broken_config_app,
        frontik_broken_init_async_app,
        frontik_consul_mock_app,
        frontik_no_debug_app,
        frontik_re_app,
        frontik_test_app,
        frontik_test_app_with_dev_router,
    )

    frontik_broken_config_app.stop()
    frontik_broken_init_async_app.stop()
    frontik_no_debug_app.stop()
    frontik_re_app.stop()
    frontik_test_app.stop()
    frontik_test_app_with_dev_router.stop()
    frontik_balancer_app.stop()
    frontik_broken_balancer_app.stop()
    frontik_consul_mock_app.stop()


@pytest.fixture(scope='session', autouse=True)
def _bootstrap_logging():
    options.stderr_log = True
    bootstrap_core_logging(options.log_level, options.log_json, options.suppressed_loggers)


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

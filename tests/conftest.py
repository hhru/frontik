import pytest


@pytest.fixture(scope='session', autouse=True)
def teardown_module():
    yield

    from tests.instances import (
        frontik_consul_mock_app,
        frontik_broken_config_app, frontik_broken_init_async_app,
        frontik_no_debug_app, frontik_re_app, frontik_test_app,
        frontik_balancer_app, frontik_broken_balancer_app,
    )

    frontik_broken_config_app.stop()
    frontik_broken_init_async_app.stop()
    frontik_no_debug_app.stop()
    frontik_re_app.stop()
    frontik_test_app.stop()
    frontik_balancer_app.stop()
    frontik_broken_balancer_app.stop()
    frontik_consul_mock_app.stop()

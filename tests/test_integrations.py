import time
import unittest

import requests

from .instances import FrontikTestInstance, common_frontik_start_options


class IntegrationTestCase(unittest.TestCase):

    async def async_start(self):
        self.frontik_multiple_worker_app.start()

    def setUp(self):
        self.frontik_multiple_worker_app = FrontikTestInstance(
            f'./frontik-test --app=tests.projects.no_debug_app {common_frontik_start_options} '
            f' --config=tests/projects/frontik_no_debug.cfg --workers=3 --consul_enabled=False --fail_test_integration=True')

    def tearDown(self):
        self.frontik_multiple_worker_app.stop()

    def test_server_not_bound_before_integrations_ok(self):
        def assert_app_start(instance):
            for i in range(10):
                try:
                    time.sleep(0.2)
                    response = instance.get_page('status')
                    self.assertNotEqual(response.status_code, 200)
                except requests.RequestException as re:
                    pass
        self.frontik_multiple_worker_app.start_with_check(assert_app_start)



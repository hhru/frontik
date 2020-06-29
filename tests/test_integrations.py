import time
import unittest

import requests

from .instances import FrontikTestInstance, common_frontik_start_options


class IntegrationTestCase(unittest.TestCase):

    def setUp(self):
        self.frontik_multiple_worker_app = FrontikTestInstance(
            f'./frontik-test --app=tests.projects.broken_integration.target_app {common_frontik_start_options} '
            f' --config=tests/projects/frontik_consul_mock.cfg --workers=3')

    def tearDown(self):
        self.frontik_multiple_worker_app.stop()

    def test_server_not_bound_before_integrations_ok(self):
        def assert_app_start(instance):
            # keep in relevance to tests.projects.broken_integration.target_app
            for i in range(11):
                try:
                    time.sleep(0.1)
                    response = instance.get_page('status')
                    self.assertNotEqual(response.status_code, 200)
                except requests.RequestException:
                    pass
        self.frontik_multiple_worker_app.start_with_check(assert_app_start)

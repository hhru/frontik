import time
import unittest

import requests

from tests import FRONTIK_ROOT
from tests.instances import FrontikTestInstance, common_frontik_start_options

FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'
TEST_PROJECTS = f'{FRONTIK_ROOT}/tests/projects'


class TestIntegrations(unittest.TestCase):
    def setUp(self):
        self.frontik_multiple_worker_app = FrontikTestInstance(
            f'{FRONTIK_RUN} --app=tests.projects.broken_integration.target_app.TestApplication '
            f'{common_frontik_start_options} --config={TEST_PROJECTS}/frontik_consul_mock.cfg --workers=3',
        )

    def tearDown(self):
        self.frontik_multiple_worker_app.stop()

    def test_server_not_bound_before_integrations(self):
        def assert_app_start(instance):
            # keep in relevance to tests.projects.broken_integration.target_app
            for _i in range(11):
                try:
                    time.sleep(0.1)
                    response = instance.get_page('status')
                    self.assertNotEqual(response.status_code, 200)
                except requests.RequestException:
                    pass

        self.frontik_multiple_worker_app.start_with_check(assert_app_start)

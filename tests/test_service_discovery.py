import sys
import unittest

import pytest

from tests import FRONTIK_ROOT
from tests.instances import FrontikTestInstance, common_frontik_start_options

FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'
TEST_PROJECTS = f'{FRONTIK_ROOT}/tests/projects'


class TestServiceDiscovery(unittest.TestCase):
    def setUp(self) -> None:
        self.consul_mock = FrontikTestInstance(
            f'{FRONTIK_RUN} --app=tests.projects.consul_mock_app {common_frontik_start_options} '
            f' --config={TEST_PROJECTS}/frontik_consul_mock.cfg',
        )
        self.consul_mock.start()
        self.frontik_single_worker_app = FrontikTestInstance(
            f'{FRONTIK_RUN} --app=tests.projects.no_debug_app {common_frontik_start_options} '
            f' --config={TEST_PROJECTS}/frontik_no_debug.cfg --consul_port={self.consul_mock.port} '
            f' --consul_enabled=True'
            f' --fail_start_on_empty_upstream=False',
        )
        self.frontik_multiple_worker_app = FrontikTestInstance(
            f'{FRONTIK_RUN} --app=tests.projects.no_debug_app {common_frontik_start_options} '
            f' --config={TEST_PROJECTS}/frontik_no_debug.cfg --consul_port={self.consul_mock.port} --workers=3'
            f' --consul_enabled=True'
            f' --fail_start_on_empty_upstream=False',
        )

    def tearDown(self) -> None:
        self.frontik_single_worker_app.stop()
        self.frontik_multiple_worker_app.stop()
        self.consul_mock.stop()

    def test_single_worker_de_registration(self):
        self.frontik_single_worker_app.start()
        self.frontik_single_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat')['put_page']
        self.assertEqual(registration_call_count, 1, 'Application should register only once')
        deregistration_call_count = self.consul_mock.get_page_json('call_deregistration_stat')['put_page']
        self.assertEqual(deregistration_call_count, 1, 'Application should deregister only once')

    def test_single_worker_de_registration_async(self):
        self.frontik_single_worker_app.start()
        self.frontik_single_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat_async')['put_page']
        self.assertEqual(registration_call_count, 1, 'Application should register only once')
        deregistration_call_count = self.consul_mock.get_page_json('call_deregistration_stat_async')['put_page']
        self.assertEqual(deregistration_call_count, 1, 'Application should deregister only once')

    @pytest.mark.skipif(sys.platform == 'darwin', reason="can't os.pipe2 on macos")
    def test_multiple_worker_de_registration(self):
        self.frontik_multiple_worker_app.start()
        self.frontik_multiple_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat')['put_page']
        self.assertEqual(registration_call_count, 1, 'Application should register only once')
        deregistration_call_count = self.consul_mock.get_page_json('call_deregistration_stat')['put_page']
        self.assertEqual(deregistration_call_count, 1, 'Application should deregister only once')

    @pytest.mark.skipif(sys.platform == 'darwin', reason="can't os.pipe2 on macos")
    def test_multiple_worker_de_registration_async(self):
        self.frontik_multiple_worker_app.start()
        self.frontik_multiple_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat_async')['put_page']
        self.assertEqual(registration_call_count, 1, 'Application should register only once')
        deregistration_call_count = self.consul_mock.get_page_json('call_deregistration_stat_async')['put_page']
        self.assertEqual(deregistration_call_count, 1, 'Application should deregister only once')

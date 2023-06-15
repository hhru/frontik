import time
import unittest

from .instances import FrontikTestInstance, common_frontik_start_options


class ConsulRegistrationTestCase(unittest.TestCase):

    def setUp(self):
        self.consul_mock = FrontikTestInstance(
            f'./frontik-test --app=tests.projects.consul_mock_app {common_frontik_start_options} '
            ' --config=tests/projects/frontik_consul_mock.cfg')
        self.consul_mock.start()
        self.frontik_single_worker_app = FrontikTestInstance(
            f'./frontik-test --app=tests.projects.no_debug_app {common_frontik_start_options} '
            f' --config=tests/projects/frontik_no_debug.cfg --consul_port={self.consul_mock.port} '
            f' --consul_enabled=True'
            f' --fail_start_on_empty_upstream=False')
        self.frontik_multiple_worker_app = FrontikTestInstance(
            f'./frontik-test --app=tests.projects.no_debug_app {common_frontik_start_options} '
            f' --config=tests/projects/frontik_no_debug.cfg --consul_port={self.consul_mock.port} --workers=3'
            f' --consul_enabled=True'
            f' --fail_start_on_empty_upstream=False')
        self.frontik_multiple_worker_app_timeout_barrier = FrontikTestInstance(
            f'./frontik-test --app=tests.projects.no_debug_app {common_frontik_start_options} '
            f' --config=tests/projects/frontik_no_debug.cfg --consul_port={self.consul_mock.port} --workers=3'
            f' --init_workers_timeout_sec=0'
            f' --consul_enabled=True'
            f' --fail_start_on_empty_upstream=False')

    def tearDown(self):
        self.frontik_single_worker_app.stop()
        self.frontik_multiple_worker_app.stop()
        self.frontik_multiple_worker_app_timeout_barrier.stop()
        self.consul_mock.stop()

    def test_single_worker_registration(self):
        self.frontik_single_worker_app.start()
        self.frontik_single_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat')['put_page']
        self.assertEqual(registration_call_count, 1, 'Application should register only once')

    def test_multiple_worker_registration_ok(self):
        self.frontik_multiple_worker_app.start()
        self.frontik_multiple_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat')['put_page']
        self.assertEqual(registration_call_count, 1, 'Application should register only once')

    def test_multiple_worker_not_registration(self):
        self.frontik_multiple_worker_app_timeout_barrier.start_with_check(lambda _: None)

        for i in range(50):
            time.sleep(0.1)
            if not self.frontik_multiple_worker_app_timeout_barrier.is_alive():
                break
        else:
            raise Exception('application didn\'t stop')

        registration_call_count = self.consul_mock.get_page_json('call_registration_stat')
        self.assertEqual(registration_call_count, {}, 'Application should not register')

        self.frontik_multiple_worker_app_timeout_barrier.stop()

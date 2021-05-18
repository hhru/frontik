import time
import unittest

from requests.exceptions import ConnectionError

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
            f' --consul_enabled=True')
        self.frontik_multiple_worker_app = FrontikTestInstance(
            f'./frontik-test --app=tests.projects.no_debug_app {common_frontik_start_options} '
            f' --config=tests/projects/frontik_no_debug.cfg --consul_port={self.consul_mock.port} --workers=3'
            f' --consul_enabled=True')
        self.frontik_multiple_worker_app_timeout_barrier = FrontikTestInstance(
            f'./frontik-test --app=tests.projects.no_debug_app {common_frontik_start_options} '
            f' --config=tests/projects/frontik_no_debug.cfg --consul_port={self.consul_mock.port} --workers=3'
            f' --init_workers_timeout_sec=0'
            f' --consul_enabled=True')

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

    def test_multiple_worker_registration(self):
        self.frontik_multiple_worker_app.start()
        self.frontik_multiple_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat')['put_page']
        self.assertEqual(registration_call_count, 1, 'Application should register only once')

    def test_multiple_worker_not_registration(self):
        def check_function(instance):
            for i in range(10):
                try:
                    time.sleep(0.2)
                    response = instance.get_page('status')
                    if response.status_code == 200:
                        return
                except Exception:
                    pass

            def check_registered_status():
                instance.get_page('check_workers_count_down')

            self.assertRaises(ConnectionError, check_registered_status)

        self.frontik_multiple_worker_app_timeout_barrier.start_with_check(check_function)
        self.frontik_multiple_worker_app_timeout_barrier.stop()

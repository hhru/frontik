import unittest
from time import sleep

from .instances import FrontikTestInstance


class ServiceDiscoveryTestCase(unittest.TestCase):

    def setUp(self):
        self.consul_mock = FrontikTestInstance(
            './frontik-test --app=tests.projects.consul_mock_app --log_dir=.'
            ' --config=tests/projects/frontik_consul_mock.cfg'
        )
        self.consul_mock.start()
        self.frontik_single_worker_app = FrontikTestInstance(
            './frontik-test --app=tests.projects.no_debug_app --log_dir=.'
            ' --config=tests/projects/frontik_no_debug.cfg --consul_port={}'.format(self.consul_mock.port))
        self.frontik_multiple_worker_app = FrontikTestInstance(
            './frontik-test --app=tests.projects.no_debug_app --log_dir=.'
            ' --config=tests/projects/frontik_no_debug.cfg --consul_port={} --workers=3'.format(self.consul_mock.port))

    def tearDown(self):
        self.frontik_single_worker_app.stop()
        self.frontik_multiple_worker_app.stop()
        self.consul_mock.stop()

    def test_single_worker_de_registration(self):
        self.frontik_single_worker_app.start()
        self.frontik_single_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat')['put_page']
        if registration_call_count != 1:
            self.fail('Application should register only once')
        deregistration_call_count = self.consul_mock.get_page_json('call_deregistration_stat')['put_page']
        if deregistration_call_count != 1:
            self.fail('Application should deregister only once')

    def test_multiple_worker_de_registration(self):
        self.frontik_multiple_worker_app.start()
        self.frontik_multiple_worker_app.stop()
        registration_call_count = self.consul_mock.get_page_json('call_registration_stat')['put_page']
        if registration_call_count != 1:
            self.fail('Application should register only once')
        deregistration_call_count = self.consul_mock.get_page_json('call_deregistration_stat')['put_page']
        if deregistration_call_count != 1:
            self.fail('Application should deregister only once')

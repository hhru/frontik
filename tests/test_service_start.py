import unittest

from .instances import FrontikTestInstance


class TestServiceStart(unittest.TestCase):
    def app_run(self, parameters):
        service = FrontikTestInstance(parameters)
        service.start()
        response = service.get_page('status')
        self.assertEqual(response.status_code, 200)
        service.stop()

    def test_with_only_app(self):
        self.app_run('./frontik-test --app=tests.projects.test_app'
                     f' --syslog=false --consul_enabled=False')

    def test_with_app_class(self):
        self.app_run(f'./frontik-test --app=test-app --app_class=tests.projects.test_app.TestApplication'
                     f' --syslog=false --consul_enabled=False')

import unittest

from tests.instances import FrontikTestInstance
from tests import FRONTIK_ROOT

FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'

class TestServiceStart(unittest.TestCase):
    def app_run(self, parameters: str) -> None:
        service = FrontikTestInstance(parameters)
        service.start()
        response = service.get_page('status')
        self.assertEqual(response.status_code, 200)
        service.stop()

    def test_with_only_app(self) -> None:
        self.app_run(f'{FRONTIK_RUN} --app=tests.projects.test_app'
                     f' --syslog=false --consul_enabled=False')

    def test_with_app_class(self) -> None:
        self.app_run(f'{FRONTIK_RUN} --app=test-app --app_class=tests.projects.test_app.TestApplication'
                     f' --syslog=false --consul_enabled=False')

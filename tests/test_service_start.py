import unittest

from tests import FRONTIK_ROOT
from tests.instances import FrontikTestInstance

FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'


class TestServiceStart(unittest.TestCase):
    def app_run(self, parameters: str) -> None:
        service = FrontikTestInstance(parameters)
        service.start()
        response = service.get_page('status')
        self.assertEqual(response.status_code, 200)
        service.stop()

    def test_app(self) -> None:
        self.app_run(
            f'{FRONTIK_RUN} --app=tests.projects.test_app.TestApplication --syslog=false --consul_enabled=False',
        )

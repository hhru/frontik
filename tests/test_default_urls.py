import json

import pytest

from frontik.app import FrontikApplication
from frontik.testing import FrontikTestBase


class AppWithVersion(FrontikApplication):
    def application_version(self) -> int:
        return '0.1.0'


class TestDefaultUrls(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return AppWithVersion(app_module_name=None)

    async def test_version(self, frontik_app: AppWithVersion) -> None:
        xml = await self.fetch_xml('/version')
        test_app_version = xml.xpath(f'application[@name="{frontik_app.app_module_name}"]/version')[0]

        assert xml.tag == 'versions'
        assert test_app_version.text == '0.1.0'

    async def test_status(self) -> None:
        response = await self.fetch('/status')

        assert response.headers['Content-Type'].startswith('application/json')

        json_response = json.loads(response.raw_body)
        assert 'uptime' in json_response
        assert json_response['app_version'] == '0.1.0'

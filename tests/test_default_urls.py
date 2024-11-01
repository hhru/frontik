import json

import pytest

from frontik.app import FrontikApplication
from frontik.testing import FrontikTestBase


class TestDefaultUrls(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication()

    async def test_version(self) -> None:
        xml = await self.fetch_xml('/version')
        test_app_version = xml.xpath('application[@name="frontik.app"]/version')[0]

        assert xml.tag == 'versions'
        assert test_app_version.text == 'unknown'

    async def test_status(self) -> None:
        response = await self.fetch('/status')

        assert response.headers['Content-Type'].startswith('application/json')

        json_response = json.loads(response.raw_body)
        assert 'uptime' in json_response

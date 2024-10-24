import json

from frontik.testing import FrontikTestBase


class TestDefaultUrls(FrontikTestBase):
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

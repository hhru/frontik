import json
import unittest

from .instances import frontik_debug


class TestDefaultUrls(unittest.TestCase):
    def test_versions(self):
        xml = frontik_debug.get_page_xml('version')
        test_app_version = xml.xpath('applications/application[@path="/+test_app"]/app-version/@number')

        self.assertEqual(xml.tag, 'versions')
        self.assertIn('last version', test_app_version)

    def test_status(self):
        response = frontik_debug.get_page('status')

        self.assertEqual(response.headers['Content-Type'], 'application/json; charset=UTF-8')

        json_response = json.loads(response.content)
        self.assertIn('pages served', json_response)
        self.assertIn('http requests made', json_response)
        self.assertIn('bytes from http requests', json_response)
        self.assertIn('uptime', json_response)

import json
import unittest

from .instances import frontik_re_app, frontik_test_app


class TestDefaultUrls(unittest.TestCase):
    def test_version(self):
        xml = frontik_test_app.get_page_xml('version')
        test_app_version = xml.xpath('application[@name="tests.projects.test_app"]/app-version/@number')[0]

        self.assertEqual(xml.tag, 'versions')
        self.assertEqual('last version', test_app_version)

    def test_unknown_version(self):
        xml = frontik_re_app.get_page_xml('version')
        re_app_version = xml.findtext('application[@name="tests.projects.re_app"]/version')

        self.assertEqual('unknown', re_app_version)

    def test_no_version(self):
        xml = frontik_re_app.get_page_xml('version')
        re_app_version = xml.findtext('application[@name="tests.projects.re_app"]/version')

        self.assertEqual(xml.tag, 'versions')
        self.assertEqual(re_app_version, 'unknown')

    def test_status(self):
        response = frontik_test_app.get_page('status')

        self.assertEqual(response.headers['Content-Type'], 'application/json; charset=UTF-8')

        json_response = json.loads(response.content)
        self.assertIn('uptime', json_response)

        self.assertIn('workers', json_response)
        self.assertIn('total', json_response['workers'])
        self.assertIn('free', json_response['workers'])

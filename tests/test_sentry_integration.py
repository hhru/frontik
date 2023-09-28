import unittest
from typing import Any

import requests

from tests.instances import frontik_re_app, frontik_test_app


class TestSentryIntegration(unittest.TestCase):
    def test_sentry_exception(self):
        frontik_test_app.get_page('api/2/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error?ip=127.0.0.77&extra_key=extra_val')

        sentry_events = self._get_sentry_exceptions('My_sentry_exception')
        self.assertEqual(len(sentry_events), 1)

        event = sentry_events[0]
        self.assertEqual(len(event['breadcrumbs']['values']), 0)
        self.assertIsNone(event.get('modules'))
        self.assertEqual(event['request']['query_string'], 'ip=127.0.0.77&extra_key=extra_val')
        self.assertEqual(event['user']['real_ip'], '127.0.0.77')
        self.assertEqual(event['extra']['extra_key'], 'extra_val')

        # second request for check that sentry scope was overwritten
        frontik_test_app.get_page('sentry_error')
        sentry_events = self._get_sentry_exceptions('My_sentry_exception')
        self.assertEqual(len(sentry_events), 2)

        event = sentry_events[1]
        self.assertIsNone(event['user'].get('real_ip'))
        self.assertIsNone(event.get('extra'))

    def test_sentry_message(self):
        frontik_test_app.get_page('api/2/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error', method=requests.put, headers={'MaHeaderKey': 'MaHeaderValue'})

        sentry_events = self._get_sentry_messages()
        sentry_events = list(filter(lambda e: e['message'] == 'sentry_message', sentry_events))
        self.assertEqual(len(sentry_events), 1)

        event = sentry_events[0]
        self.assertEqual(len(event['breadcrumbs']['values']), 0)
        self.assertIsNone(event.get('modules'))
        self.assertTrue(event['request']['url'].endswith('/sentry_error'))
        self.assertEqual(event['request']['method'], 'PUT')
        self.assertEqual(event['request']['headers']['Maheaderkey'], 'MaHeaderValue')
        self.assertEqual(event['extra']['extra_key'], 'extra_value')
        self.assertEqual(event['user']['id'], '123456')

    def test_sentry_http_error(self):
        frontik_test_app.get_page('api/2/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error', method=requests.post)

        sentry_events = self._get_sentry_exceptions('my_HTTPError')
        self.assertEqual(len(sentry_events), 0, 'HTTPError must not be sent to Sentry')

    def test_sentry_not_configured(self):
        self.assertEqual(200, frontik_re_app.get_page('sentry_not_configured').status_code)

    @staticmethod
    def _get_sentry_messages() -> list[dict[str, Any]]:
        sentry_json = frontik_test_app.get_page_json('api/2/store')
        return sentry_json['exceptions']

    @staticmethod
    def _get_sentry_exceptions(name: str) -> list[dict[str, Any]]:
        sentry_json = frontik_test_app.get_page_json('api/2/store')
        return list(filter(lambda e: e['exception']['values'][0]['value'] == name, sentry_json['exceptions']))

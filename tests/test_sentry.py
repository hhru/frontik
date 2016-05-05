# coding=utf-8

import base64
import json
import logging
import unittest
import zlib

import requests

from frontik.loggers.sentry import has_raven

from . import py3_skip
from .instances import frontik_re_app, frontik_test_app


@unittest.skipIf(not has_raven, 'raven library not found')
class TestSentry(unittest.TestCase):
    @py3_skip
    def test_sentry_exception(self):
        frontik_test_app.get_page('api/sentry/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error')

        for exception in self._iter_sentry_messages():
            if exception['message'] == 'Exception: Runtime exception for Sentry':
                self.assertEqual(logging.ERROR, exception['level'])
                self.assertIn('/sentry_error', exception['request']['url'])
                self.assertEqual('123456', exception['user']['id'])
                break
        else:
            self.fail('Exception not sent to Sentry')

    @py3_skip
    def test_sentry_message(self):
        frontik_test_app.get_page('api/sentry/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error', method=requests.put)

        for exception in self._iter_sentry_messages():
            if exception['message'] == 'Message for Sentry':
                self.assertEqual(logging.ERROR, exception['level'])
                self.assertEqual('PUT', exception['request']['method'])
                self.assertIn('/sentry_error', exception['request']['url'])
                self.assertEqual('123456', exception['user']['id'])
                break
            else:
                self.fail(exception)
        else:
            self.fail('Message not sent to Sentry')

    @py3_skip
    def test_sentry_http_error(self):
        frontik_test_app.get_page('api/sentry/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error', method=requests.post)

        for exception in self._iter_sentry_messages():
            if 'HTTPError for Sentry' in exception['message']:
                self.fail('HTTPError must not be sent to Sentry')

    @py3_skip
    def test_sentry_not_configured(self):
        self.assertEqual(200, frontik_re_app.get_page('sentry_not_configured').status_code)

    def _iter_sentry_messages(self):
        sentry_json = frontik_test_app.get_page_json('api/sentry/store')

        for encoded_exception in sentry_json['exceptions']:
            yield json.loads(zlib.decompress(base64.b64decode(encoded_exception)).decode('utf8'))

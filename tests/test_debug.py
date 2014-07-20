# coding=utf-8

import unittest

from frontik.handler_debug import request_to_curl_string
from frontik.util import make_get_request, make_post_request, make_put_request


class TestDebug(unittest.TestCase):
    def test_curl_string_get(self):
        request = make_get_request(
            'http://test.com/path',
            data={'param': 'value'},
            headers={'Accept': 'application/json'}
        )

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X GET 'http://test.com/path?param=value' -H 'Accept: application/json'"
        )

    def test_curl_string_post(self):
        request = make_post_request('http://test.com/path', data={'param': 'value'})

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 11' "
            "-H 'Content-Type: application/x-www-form-urlencoded' --data 'param=value'"
        )

    def test_curl_string_put(self):
        request = make_put_request('http://test.com/path', data='DATA', content_type='text/plain')

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X PUT 'http://test.com/path' -H 'Content-Length: 4' -H 'Content-Type: text/plain' --data 'DATA'"
        )

    def test_curl_string_binary(self):
        request = make_post_request('http://test.com/path', data=u'тест', content_type='text/plain')

        self.assertEqual(
            request_to_curl_string(request),
            "echo -e '\\xd1\\x82\\xd0\\xb5\\xd1\\x81\\xd1\\x82' | "
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 4' -H 'Content-Type: text/plain' --data-binary @-"
        )

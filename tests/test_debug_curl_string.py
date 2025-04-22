import unittest

from http_client.request_response import BalancedHttpRequest

from frontik import media_types
from frontik.debug import request_to_curl_string


class TestCurlString(unittest.TestCase):
    def test_curl_string_get(self):
        request = BalancedHttpRequest(
            host='http://test.com',
            path='/path',
            name='test',
            method='GET',
            data={'param': 'value'},
            headers={'Accept': media_types.APPLICATION_JSON},
        )

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X GET 'http://test.com/path?param=value' -H 'Accept: application/json'",
        )

    def test_curl_string_post(self):
        request = BalancedHttpRequest(
            host='http://test.com',
            path='/path',
            name='test',
            method='POST',
            data={'param': 'value'},
        )

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 11' --data 'param=value'",
        )

    def test_curl_string_put(self):
        request = BalancedHttpRequest(
            host='http://test.com',
            path='/path',
            name='test',
            data='DATA',
            method='PUT',
            content_type=media_types.TEXT_PLAIN,
        )

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X PUT 'http://test.com/path' -H 'Content-Length: 4' -H 'Content-Type: text/plain' --data 'DATA'",
        )

    def test_curl_string_binary(self):
        request = BalancedHttpRequest(
            host='http://test.com',
            path='/path',
            name='test',
            data='тест'.encode(),
            method='POST',
            content_type=media_types.TEXT_PLAIN,
        )

        self.assertEqual(
            request_to_curl_string(request),
            "echo -e '\\xd1\\x82\\xd0\\xb5\\xd1\\x81\\xd1\\x82' | "
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 8' -H 'Content-Type: text/plain' "
            '--data-binary @-',
        )

import unittest

from http_client.request_response import RequestBuilder, USER_AGENT_HEADER

from frontik import media_types
from frontik.debug import request_to_curl_string


class TestCurlString(unittest.TestCase):
    def test_curl_string_get(self):
        request = RequestBuilder(
            'http://test.com',
            'test',
            '/path',
            'test',
            data={'param': 'value'},
            headers={'Accept': media_types.APPLICATION_JSON},
        )

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X GET 'http://test.com/path?param=value' "
            "-H 'Accept: application/json' -H '{}: test'".format(USER_AGENT_HEADER),
        )

    def test_curl_string_post(self):
        request = RequestBuilder('http://test.com', 'test', '/path', 'test', data={'param': 'value'}, method='POST')

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 11' "
            "-H 'Content-Type: application/x-www-form-urlencoded' "
            "-H '{}: test' --data 'param=value'".format(USER_AGENT_HEADER),
        )

    def test_curl_string_put(self):
        request = RequestBuilder(
            'http://test.com', 'test', '/path', 'test', data='DATA', method='PUT', content_type=media_types.TEXT_PLAIN
        )

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X PUT 'http://test.com/path' -H 'Content-Length: 4' -H 'Content-Type: text/plain' "
            "-H '{}: test' --data 'DATA'".format(USER_AGENT_HEADER),
        )

    def test_curl_string_binary(self):
        request = RequestBuilder(
            'http://test.com', 'test', '/path', 'test', data='тест', method='POST', content_type=media_types.TEXT_PLAIN
        )

        self.assertEqual(
            request_to_curl_string(request),
            "echo -e '\\xd1\\x82\\xd0\\xb5\\xd1\\x81\\xd1\\x82' | "
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 8' -H 'Content-Type: text/plain' "
            "-H '{}: test' --data-binary @-".format(USER_AGENT_HEADER),
        )

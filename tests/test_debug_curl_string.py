import unittest

# noinspection PyUnresolvedReferences
import frontik.options

from frontik.debug import request_to_curl_string
from frontik.http_client import BalancedHttpRequest, Upstream


class CurlStringTestCase(unittest.TestCase):
    def test_curl_string_get(self):
        request = BalancedHttpRequest('http://test.com', Upstream.get_single_host_upstream(), '/path', 'test',
                                      data={'param': 'value'},
                                      headers={'Accept': 'application/json'}).make_request()

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X GET 'http://test.com/path?param=value' -H 'Accept: application/json'"
        )

    def test_curl_string_post(self):
        request = BalancedHttpRequest('http://test.com', Upstream.get_single_host_upstream(), '/path', 'test',
                                      data={'param': 'value'},
                                      method='POST').make_request()

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 11' "
            "-H 'Content-Type: application/x-www-form-urlencoded' --data 'param=value'"
        )

    def test_curl_string_put(self):
        request = BalancedHttpRequest('http://test.com', Upstream.get_single_host_upstream(), '/path', 'test',
                                      data='DATA',
                                      method='PUT',
                                      content_type='text/plain').make_request()

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X PUT 'http://test.com/path' -H 'Content-Length: 4' -H 'Content-Type: text/plain' --data 'DATA'"
        )

    def test_curl_string_binary(self):
        request = BalancedHttpRequest('http://test.com', Upstream.get_single_host_upstream(), '/path', 'test',
                                      data='тест',
                                      method='POST',
                                      content_type='text/plain').make_request()

        self.assertEqual(
            request_to_curl_string(request),
            "echo -e '\\xd1\\x82\\xd0\\xb5\\xd1\\x81\\xd1\\x82' | "
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 8' -H 'Content-Type: text/plain' --data-binary @-"
        )

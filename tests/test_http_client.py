# coding=utf-8

import unittest
from lxml import etree

from .instances import frontik_test_app


class TestHttpClient(unittest.TestCase):
    def test_post_url_simple(self):
        xml = frontik_test_app.get_page_xml('http_client/post_simple')
        self.assertEqual(xml.text, '42')

    def test_post_url_mfd(self):
        response = frontik_test_app.get_page('http_client/post_url')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(etree.fromstring(response.content.encode('utf-8')).text)

    def test_fib0(self):
        xml = frontik_test_app.get_page_xml('http_client/fibonacci?n=0')
        self.assertEqual(xml.text, '1')

    def test_fib2(self):
        xml = frontik_test_app.get_page_xml('http_client/fibonacci?n=2')
        self.assertEqual(xml.text, '2')

    def test_fib6(self):
        xml = frontik_test_app.get_page_xml('http_client/fibonacci?n=6')
        self.assertEqual(xml.text, '13')

    def test_timeout(self):
        xml = frontik_test_app.get_page_xml('http_client/long_page_request')
        self.assertEqual(xml.text, 'error')

    def test_error_in_cb(self):
        """
        when json or xml parsing error ocuurs, we must send None into callback
        """
        xml = frontik_test_app.get_page_xml('bad_page')
        self.assertEqual(xml.text, '4242')

    def test_add_to_finish_group(self):
        text = frontik_test_app.get_page_text('http_client/add_to_finish_group')
        self.assertEqual(text, '{"get": true}')

    def test_parse_response(self):
        text = frontik_test_app.get_page_text('http_client/parse_response')
        self.assertEqual(
            text, '{"post": true, "delete": "deleted", "error": {"reason": "HTTP 400: Bad Request", "code": 400}}'
        )

    def test_custom_headers(self):
        json = frontik_test_app.get_page_json('http_client/custom_headers')
        self.assertEqual(json['X-Foo'], 'Bar')

    def test_group(self):
        text = frontik_test_app.get_page_text('http_client/group')
        self.assertEqual(text, '{"1": {"1": "yay"}, "2": {"2": "yay"}, "final_callback_called": true}')

    def test_group_with_failing_request(self):
        response = frontik_test_app.get_page('http_client/group?fail=true')
        self.assertEqual(response.status_code, 500)

    def test_error_callback_on_error(self):
        text = frontik_test_app.get_page_text('http_client/error_callback?code=500')
        self.assertEqual(
            text, '<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<doc frontik="true">Error callback works</doc>'
        )

    def test_error_callback_on_204(self):
        text = frontik_test_app.get_page_text('http_client/error_callback?code=204')
        self.assertEqual(
            text, '<?xml version=\'1.0\' encoding=\'utf-8\'?>\n'
                  '<doc frontik="true">Success callback is called only if there was no error</doc>'
        )

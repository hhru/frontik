# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestHttpClient(unittest.TestCase):
    def test_post_url_simple(self):
        xml = frontik_test_app.get_page_xml('post_simple')
        self.assertEqual(xml.text, '42')

    def test_post_url_mfd(self):
        xml = frontik_test_app.get_page_xml('post_url')
        self.assertIsNone(xml.text)

    def test_fib0(self):
        xml = frontik_test_app.get_page_xml('fib/?n=0')
        self.assertEqual(xml.text, '1')

    def test_fib2(self):
        xml = frontik_test_app.get_page_xml('fib/?n=2')
        self.assertEqual(xml.text, '2')

    def test_fib6(self):
        xml = frontik_test_app.get_page_xml('fib/?n=6')
        self.assertEqual(xml.text, '13')

    def test_timeout(self):
        xml = frontik_test_app.get_page_xml('long_page_request')
        self.assertEqual(xml.text, 'error')

    def test_error_in_cb(self):
        """
        when json or xml parsing error ocuurs, we must send None into callback
        """
        xml = frontik_test_app.get_page_xml('bad_page')
        self.assertEqual(xml.text, '4242')

    def test_check_finished(self):
        text = frontik_test_app.get_page_text('check_finished')
        self.assertEqual(text, 'Callback not called')

        # Check that callback has not been called at later IOLoop iteration

        text = frontik_test_app.get_page_text('check_finished')
        self.assertEqual(text, 'Callback not called')

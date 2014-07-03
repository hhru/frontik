# coding=utf-8

import unittest

from .instances import frontik_debug


class TestHttpClient(unittest.TestCase):
    def test_post_url_simple(self):
        xml = frontik_debug.get_page_xml('test_app/post_simple/?port={port}')
        self.assertEquals(xml.text, '42')

    def test_post_url_mfd(self):
        xml = frontik_debug.get_page_xml('test_app/post_url/?port={port}')
        self.assertIsNone(xml.text)

    def test_fib0(self):
        xml = frontik_debug.get_page_xml('test_app/fib/?port={port}&n=0')
        self.assertEquals(xml.text, '1')

    def test_fib2(self):
        xml = frontik_debug.get_page_xml('test_app/fib/?port={port}&n=2')
        self.assertEquals(xml.text, '2')

    def test_fib6(self):
        xml = frontik_debug.get_page_xml('test_app/fib/?port={port}&n=6')
        self.assertEquals(xml.text, '13')

    def test_timeout(self):
        xml = frontik_debug.get_page_xml('test_app/long_page_request/?port={port}')
        self.assertEquals(xml.text, 'error')

    def test_error_in_cb(self):
        """
        when json or xml parsing error ocuurs, we must send None into callback
        """
        xml = frontik_debug.get_page_xml('test_app/bad_page/?port={port}')
        self.assertEquals(xml.text, '4242')

    def test_check_finished(self):
        text = frontik_debug.get_page_text('test_app/check_finished')
        self.assertEquals(text, 'Callback not called')

        # Check that callback has not been called at later IOLoop iteration

        text = frontik_debug.get_page_text('test_app/check_finished')
        self.assertEquals(text, 'Callback not called')

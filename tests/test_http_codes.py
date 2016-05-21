# coding=utf-8

import unittest

from frontik import http_codes


class ProcessStatusCodeTestCase(unittest.TestCase):
    def test_python_supported_code(self):
        self.assertEqual((404, None), http_codes.process_status_code(status_code=404))
        self.assertEqual((404, 'My reason'), http_codes.process_status_code(status_code=404, reason='My reason'))

    def test_python_maybe_unsupported_code(self):
        self.assertEqual(
            (429, 'Too Many Requests'), http_codes.process_status_code(status_code=429, reason='Too Many Requests')
        )

        self.assertEqual((429, 'My reason'), http_codes.process_status_code(status_code=429, reason='My reason'))

    def test_unknown_code(self):
        self.assertEqual((503, None), http_codes.process_status_code(status_code=999, reason=None))
        self.assertEqual((503, 'My reason'), http_codes.process_status_code(status_code=999, reason='My reason'))

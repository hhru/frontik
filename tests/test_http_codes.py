# coding: utf-8
import unittest
import httplib

from frontik.http_codes import process_status_code


class ProcessStatusCodeTestCase(unittest.TestCase):

    def test_python_supported_code(self):
        self.assertEqual((404, None), process_status_code(status_code=404, reason=None))
        self.assertEqual((404, 'My reason'), process_status_code(status_code=404, reason='My reason'))

    def test_python_unsupported_code(self):
        if 429 in httplib.responses:
            self.skipTest('current python version is supported new HTTP codes')
        self.assertEqual((429, 'Too Many Requests'), process_status_code(status_code=429, reason=None))
        self.assertEqual((429, 'My reason'), process_status_code(status_code=429, reason='My reason'))

    def test_unknown_code(self):
        self.assertEqual((503, None), process_status_code(status_code=999, reason=None))
        self.assertEqual((503, None), process_status_code(status_code=999, reason='My reason'))

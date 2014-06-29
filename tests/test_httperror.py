# coding=utf-8

import unittest

from .instances import frontik_debug


class TestExceptions(unittest.TestCase):
    def test_finish_with_httperror_200(self):
        content = frontik_debug.get_page_text('test_app/finish_page')
        self.assertEqual(content, 'success')

    def test_finish_with_httperror_401(self):
        response = frontik_debug.get_page('test_app/finish_401')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.raw.reason, 'Unauthorized')
        self.assertEqual(response.headers['WWW-Authenticate'], 'Basic realm="Secure Area"')

    def test_httperror_text(self):
        response = frontik_debug.get_page('test_app/test_exception_text?port={port}')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, 'This is just a plain text')

    def test_httperror_json(self):
        response = frontik_debug.get_page('test_app/test_exception_json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, '{"reason": "bad argument"}')

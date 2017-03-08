# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestRequestContext(unittest.TestCase):
    def test_request_context(self):
        json = frontik_test_app.get_page_json('request_context')

        self.assertEqual(json, {
            'page': 'request_context',
            'callback': 'request_context',
            'null_context_callback': None,
            'executor': None,
            'executor_wrapped': 'request_context',
            'coroutine_before_yield': 'request_context',
            'coroutine_after_yield': 'request_context'
        })

# coding=utf-8

import unittest

from frontik.testing import json_asserts

from .instances import frontik_test_app


class TestAsyncGroup(unittest.TestCase, json_asserts.JsonTestCaseMixin):
    def test_group(self):
        json = frontik_test_app.get_page_json('async_group/group')
        self.assertJsonEqual(
            json,
            {
                '1': {'1': 'yay'},
                '2': {'2': 'yay'},
                '3': {'3': 'yay'},
                'final_callback_called': True
            }
        )

    def test_group_request_fail(self):
        json = frontik_test_app.get_page_json('async_group/group?fail_request=true')
        self.assertJsonEqual(
            json,
            {
                '1': {'1': 'yay'},
                '2': {'2': 'yay'},
                '3': {'error': {'reason': 'HTTP 400: Bad Request', 'code': 400}},
                'final_callback_called': True
            }
        )

    def test_group_callback_fail(self):
        response = frontik_test_app.get_page('async_group/group?fail_callback=true')
        self.assertEqual(response.status_code, 500)

    def test_group_with_only_resolved_futures(self):
        json = frontik_test_app.get_page_json('async_group/group_with_futures')
        self.assertJsonEqual(json, {'1': {'1': 'yay'}, '2': {'2': 'yay'}, 'final_callback_called': True})

    def test_group_with_failing_future(self):
        response = frontik_test_app.get_page('async_group/group_with_futures?failed_future=true')
        self.assertEqual(response.status_code, 500)

    def test_add_to_finish_group(self):
        json = frontik_test_app.get_page_json('async_group/add_to_finish_group')
        self.assertJsonEqual(json, {'get': True})

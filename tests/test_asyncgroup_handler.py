import unittest

from .instances import frontik_test_app


class TestAsyncGroup(unittest.TestCase):
    def test_group(self):
        json = frontik_test_app.get_page_json('async_group/group')
        self.assertEqual(
            json,
            {
                '1': {'1': 'yay'},
                '2': {'2': 'yay'},
                '3': {'3': 'yay'},
                'final_callback_called': True,
                'future_callback_result': 'yay'
            }
        )

    def test_group_async(self):
        json = frontik_test_app.get_page_json('async_group/group_async')
        self.assertEqual(
            json,
            {
                '1': {'1': 'yay'},
                '2': {'2': 'yay'},
                '3': {'3': 'yay'},
                'final_callback_called': True,
                'future_callback_result': 'yay'
            }
        )

    def test_group_request_fail(self):
        json = frontik_test_app.get_page_json('async_group/group?fail_request=true')
        self.assertEqual(
            json,
            {
                '1': {'1': 'yay'},
                '2': {'2': 'yay'},
                '3': {'error': {'reason': 'HTTP 400: Bad Request', 'code': 400}},
                'final_callback_called': True,
                'future_callback_result': 'yay'
            }
        )

    def test_group_request_fail_async(self):
        json = frontik_test_app.get_page_json('async_group/group_async?fail_request=true')
        self.assertEqual(
            json,
            {
                '1': {'1': 'yay'},
                '2': {'2': 'yay'},
                '3': {'error': {'reason': 'HTTP 400: Bad Request', 'code': 400}},
                'final_callback_called': True,
                'future_callback_result': 'yay'
            }
        )

    def test_group_callback_fail(self):
        response = frontik_test_app.get_page('async_group/group?fail_callback=true')
        self.assertEqual(response.status_code, 500)

    def test_group_callback_fail_async(self):
        response = frontik_test_app.get_page('async_group/group_async?fail_callback=true')
        self.assertEqual(response.status_code, 500)

    def test_group_with_only_resolved_futures(self):
        json = frontik_test_app.get_page_json('async_group/group_with_futures')
        self.assertEqual(json, {'1': {'1': 'yay'}, '2': {'2': 'yay'}, 'final_callback_called': True})

    def test_group_with_only_resolved_futures_async(self):
        json = frontik_test_app.get_page_json('async_group/group_with_futures_async')
        self.assertEqual(json, {'1': {'1': 'yay'}, '2': {'2': 'yay'}})

    def test_group_with_failing_future(self):
        response = frontik_test_app.get_page('async_group/group_with_futures?failed_future=true')
        self.assertEqual(response.status_code, 500)

    def test_group_with_failing_future_async(self):
        response = frontik_test_app.get_page('async_group/group_with_futures_async?failed_future=true')
        self.assertEqual(response.status_code, 500)

    def test_not_waited_requests(self):
        json = frontik_test_app.get_page_json('async_group/not_waited_requests')
        self.assertEqual(json, {'get': True})

        json = frontik_test_app.get_page_json('async_group/not_waited_requests')
        self.assertEqual(json, {'post_made': True, 'put_made': True, 'delete_cancelled': True})

    def test_not_waited_requests_async(self):
        json = frontik_test_app.get_page_json('async_group/not_waited_requests_async')
        self.assertEqual(json, {'get': True})

        json = frontik_test_app.get_page_json('async_group/not_waited_requests_async')
        self.assertEqual(json, {'post_made': True, 'put_made': True, 'delete_cancelled': True})

    def test_not_waited_failed_requests(self):
        json = frontik_test_app.get_page_json('async_group/not_waited_failed_requests')
        self.assertEqual({'get': True}, json)

        json = frontik_test_app.get_page_json('async_group/not_waited_failed_requests')
        self.assertEqual({'head_failed': True, 'post_failed': True, 'put_failed': True, 'delete_failed': True}, json)

    def test_not_waited_failed_requests_async(self):
        json = frontik_test_app.get_page_json('async_group/not_waited_failed_requests_async')
        self.assertEqual({'get': True}, json)

        json = frontik_test_app.get_page_json('async_group/not_waited_failed_requests_async')
        self.assertEqual({'head_failed': True, 'post_failed': True, 'put_failed': True, 'delete_failed': True}, json)

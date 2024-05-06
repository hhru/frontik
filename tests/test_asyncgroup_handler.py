import time

from tests.instances import frontik_test_app


class TestAsyncGroup:
    def test_group(self):
        json = frontik_test_app.get_page_json('async_group/group')
        assert json == {
            '1': {'1': 'yay'},
            '2': {'2': 'yay'},
            '3': {'3': 'yay'},
            'final_callback_called': True,
            'future_callback_result': 'yay',
        }

    def test_group_request_fail(self):
        json = frontik_test_app.get_page_json('async_group/group?fail_request=true')
        assert json == {
            '1': {'1': 'yay'},
            '2': {'2': 'yay'},
            '3': {'error': {'reason': 'Bad Request', 'code': 400}},
            'final_callback_called': True,
            'future_callback_result': 'yay',
        }

    def test_group_callback_fail(self) -> None:
        response = frontik_test_app.get_page('async_group/group?fail_callback=true')
        assert response.status_code == 500

    def test_group_with_only_resolved_futures(self):
        json = frontik_test_app.get_page_json('async_group/group_with_futures')
        assert json == {'1': {'1': 'yay'}, '2': {'2': 'yay'}, 'final_callback_called': True}

    def test_group_with_failing_future(self) -> None:
        response = frontik_test_app.get_page('async_group/group_with_futures?failed_future=true')
        assert response.status_code == 500

    def test_not_waited_requests(self):
        json = frontik_test_app.get_page_json('async_group/not_waited_requests')
        assert json == {'get': True}

        time.sleep(0.1)
        json = frontik_test_app.get_page_json('async_group/not_waited_requests')
        assert json == {'post_made': True, 'delete_cancelled': True}

    def test_not_waited_failed_requests(self):
        json = frontik_test_app.get_page_json('async_group/not_waited_failed_requests')
        assert json == {'get': True}

        time.sleep(0.1)

        json = frontik_test_app.get_page_json('async_group/not_waited_failed_requests')
        assert json == {'head_failed': True, 'post_failed': True, 'put_failed': True, 'delete_failed': True}

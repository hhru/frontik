import requests

from tests.instances import frontik_test_app


class TestFailFast:
    def test_simple(self):
        json = frontik_test_app.get_page_json('fail_fast')

        assert json['put']['error'] == 'forbidden'
        assert json['post'] == {'POST': 'post'}
        assert json['preprocessor'] is True
        assert json['delete'] is None

    def test_fail_fast(self):
        response = frontik_test_app.get_page('fail_fast?fail_fast=true')

        assert response.status_code == 403
        assert response.content == b'{"fail_fast":true}'

    def test_fail_fast_unknown_method(self):
        response = frontik_test_app.get_page('fail_fast?fail_fast=true', method=requests.head)
        assert response.status_code == 405

    def test_fail_fast_without_done(self):
        response = frontik_test_app.get_page('fail_fast/fail_fast_without_done')
        assert response.status_code == 500

    def test_fail_fast_default(self):
        response = frontik_test_app.get_page('fail_fast?fail_fast_default=true&code=400', method=requests.post)
        assert response.status_code == 400

        response = frontik_test_app.get_page('fail_fast?fail_fast_default=true&code=500', method=requests.post)
        assert response.status_code == 502

    def test_future(self):
        json = frontik_test_app.get_page_json('fail_fast/future')

        future_result = json['future']
        assert future_result == 'future_result'

    def test_future_fail(self) -> None:
        response = frontik_test_app.get_page('fail_fast/future?fail_future=true')
        assert response.status_code == 500

    def test_exception_in_fail_fast(self) -> None:
        response = frontik_test_app.get_page('fail_fast?fail_fast=true&exception_in_fail_fast=true')
        assert response.status_code == 500

    def test_fail_fast_with_producer(self):
        response = frontik_test_app.get_page('fail_fast/with_postprocessors')
        assert response.status_code == 500

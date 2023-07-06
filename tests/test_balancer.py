import unittest

from tests.instances import find_free_port, frontik_balancer_app, frontik_broken_balancer_app
import pytest


# TODO unmark skipped
class TestHttpError(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frontik_balancer_app.start()
        frontik_broken_balancer_app.start()
        cls.free_port = find_free_port(from_port=10000, to_port=20000)

    def make_url(self, url):
        return (
            f'{url}?normal={frontik_balancer_app.port}&broken={frontik_broken_balancer_app.port}&free={self.free_port}'
        )

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_connect(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_connect'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'resultresultresult')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_connect_async(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_connect_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'resultresultresult')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_connect_timeout(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_connect_timeout'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'resultresultresult')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_connect_timeout_async(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_connect_timeout_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'resultresultresult')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_error(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_error'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'resultresultresult')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_error_async(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_error_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'resultresultresult')

    def test_no_retry_error(self):
        result = frontik_balancer_app.get_page(self.make_url('no_retry_error'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'no retry error')

    def test_no_retry_error_async(self):
        result = frontik_balancer_app.get_page(self.make_url('no_retry_error_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'no retry error')

    def test_no_retry_timeout(self):
        result = frontik_balancer_app.get_page(self.make_url('no_retry_timeout'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'no retry timeout')

    def test_no_retry_timeout_async(self):
        result = frontik_balancer_app.get_page(self.make_url('no_retry_timeout_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'no retry timeout')

    def test_no_available_backend(self):
        result = frontik_balancer_app.get_page(self.make_url('no_available_backend'))
        self.assertEqual(200, result.status_code)
        self.assertEqual(b'no backend available', result.content)

    def test_no_available_backend_async(self):
        result = frontik_balancer_app.get_page(self.make_url('no_available_backend_async'))
        self.assertEqual(200, result.status_code)
        self.assertEqual(b'no backend available', result.content)

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_on_timeout(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_on_timeout'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'result')

    def test_retry_on_timeout_async(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_on_timeout_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'result')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_non_idempotent(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_non_idempotent_503'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'result')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_retry_non_idempotent_async(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_non_idempotent_503_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'result')

    def test_different_datacenter(self):
        result = frontik_balancer_app.get_page(self.make_url('different_datacenter'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(b'no backend available', result.content)

    def test_different_datacenter_async(self):
        result = frontik_balancer_app.get_page(self.make_url('different_datacenter_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(b'no backend available', result.content)

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_requests_count(self):
        result = frontik_balancer_app.get_page(self.make_url('requests_count'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'3')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_requests_count_async(self):
        result = frontik_balancer_app.get_page(self.make_url('requests_count_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'3')

    @pytest.mark.skip(reason="doesn't work with native coroutines")
    def test_slow_start(self):
        result = frontik_balancer_app.get_page(self.make_url('slow_start'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'6')

    def test_slow_start_async(self):
        result = frontik_balancer_app.get_page(self.make_url('slow_start_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(b'3', result.content)

    def test_retry_count_limit(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_count_limit'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'1')

    def test_retry_count_limit_async(self):
        result = frontik_balancer_app.get_page(self.make_url('retry_count_limit_async'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'1')

    def test_speculative_retry(self):
        result = frontik_balancer_app.get_page(self.make_url('speculative_retry'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'result')

    def test_speculative_no_retry(self):
        result = frontik_balancer_app.get_page(self.make_url('speculative_no_retry'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'no retry')

    def test_upstream_profile_with_retry(self):
        result = frontik_balancer_app.get_page(self.make_url('profile_with_retry'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'result')

    def test_upstream_profile_without_retry(self):
        result = frontik_balancer_app.get_page(self.make_url('profile_without_retry'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b'no retry')

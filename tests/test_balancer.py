import unittest

from .instances import find_free_port, frontik_balancer_app, frontik_broken_balancer_app


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

    def test_retry_connect(self):
        response = frontik_balancer_app.get_page(self.make_url('retry_connect'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'resultresultresult')

    def test_retry_connect_timeout(self):
        response = frontik_balancer_app.get_page(self.make_url('retry_connect_timeout'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'resultresultresult')

    def test_retry_error(self):
        response = frontik_balancer_app.get_page(self.make_url('retry_error'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'resultresultresult')

    def test_no_retry_error(self):
        response = frontik_balancer_app.get_page(self.make_url('no_retry_error'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'no retry error')

    def test_no_retry_timeout(self):
        response = frontik_balancer_app.get_page(self.make_url('no_retry_timeout'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'no retry timeout')

    def test_no_available_backend(self):
        response = frontik_balancer_app.get_page(self.make_url('no_available_backend'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'no backend available')

    def test_deactivate(self):
        response = frontik_balancer_app.get_page(self.make_url('deactivate'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'deactivated activated')

    def test_retry_on_timeout(self):
        response = frontik_balancer_app.get_page(self.make_url('retry_on_timeout'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'result')

    def test_retry_non_idempotent(self):
        response = frontik_balancer_app.get_page(self.make_url('retry_non_idempotent_503'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'result')

    def test_retry_to_different_rack(self):
        response = frontik_balancer_app.get_page(self.make_url('retry_to_different_rack'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'result')

    def test_different_datacenter(self):
        response = frontik_balancer_app.get_page(self.make_url('different_datacenter'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'no backend available')

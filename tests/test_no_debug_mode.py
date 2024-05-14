from tests.instances import create_basic_auth_header, frontik_no_debug_app


class TestNonDebugMode:
    def test_simple(self):
        html = frontik_no_debug_app.get_page_text('simple')
        assert '<h1>ok</h1>' in html

    def test_basic_auth_fail(self):
        response = frontik_no_debug_app.get_page('basic_auth')
        assert response.status_code == 401

    def test_basic_auth_fail_on_wrong_pass(self):
        response = frontik_no_debug_app.get_page(
            'basic_auth',
            headers={'Authorization': create_basic_auth_header('user:bad')},
        )

        assert response.status_code == 401

    def test_basic_auth_pass(self):
        response = frontik_no_debug_app.get_page(
            'basic_auth',
            headers={'Authorization': create_basic_auth_header('user:god')},
        )

        assert response.status_code == 200
        assert response.content == b'{"authenticated":true}'

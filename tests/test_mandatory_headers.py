from tests.instances import frontik_test_app


class TestPostprocessors:
    def test_set_mandatory_headers(self):
        response = frontik_test_app.get_page('mandatory_headers?test_mandatory_headers')
        assert response.status_code == 500
        assert response.headers.get('TEST_HEADER') == 'TEST_HEADER_VALUE'
        assert response.cookies.get('TEST_COOKIE') == 'TEST_HEADER_COOKIE'  # type: ignore

    def test_mandatory_headers_are_lost(self) -> None:
        response = frontik_test_app.get_page('mandatory_headers?test_without_mandatory_headers')
        assert response.status_code == 500
        assert response.headers.get('TEST_HEADER') is None
        assert response.headers.get('TEST_COOKIE') is None

    def test_mandatory_headers_are_cleared(self) -> None:
        response = frontik_test_app.get_page('mandatory_headers?test_clear_set_mandatory_headers')
        assert response.status_code == 500
        assert response.headers.get('TEST_HEADER') is None
        assert response.headers.get('TEST_COOKIE') is None

    def test_clear_not_set_headers_does_not_faile(self) -> None:
        response = frontik_test_app.get_page('mandatory_headers?test_clear_not_set_headers')
        assert response.status_code == 500
        assert response.headers.get('TEST_HEADER') is None
        assert response.headers.get('TEST_COOKIE') is None

    def test_invalid_mandatory_cookie(self):
        response = frontik_test_app.get_page('mandatory_headers?test_invalid_mandatory_cookie')
        assert response.status_code == 400
        assert response.headers.get('TEST_COOKIE') is None

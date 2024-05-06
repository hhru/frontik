from tests.instances import frontik_test_app


class TestHandler:
    def test_error_in_yield(self) -> None:
        response = frontik_test_app.get_page('error_yield')
        assert response.status_code == 500

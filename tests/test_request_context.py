from tests.instances import frontik_test_app


class TestRequestContext:
    def test_request_context(self):
        json = frontik_test_app.get_page_json('request_context')

        controller = 'tests.projects.test_app.pages.request_context.get_page'

        assert json == {
            'page': controller,
            'callback': controller,
            'coroutine_before_yield': controller,
            'coroutine_after_yield': controller,
        }

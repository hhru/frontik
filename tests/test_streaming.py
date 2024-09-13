from tests.instances import frontik_test_app


class TestStreaming:
    def test_streaming_response(self):
        response = frontik_test_app.get_page('stream')
        assert response.headers['content-type'] == 'text/plain'
        assert response.content == b'response+second_part'

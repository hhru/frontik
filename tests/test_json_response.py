import json

from tests.instances import frontik_test_app


class TestJsonResponse:
    def test_json(self):
        response = frontik_test_app.get_page('json_page', notpl=True)
        assert response.headers['content-type'].startswith('application/json') is True

        data = json.loads(response.content)
        assert data['req1']['result'] == '1'
        assert data['req2']['result'] == '2'

    def test_invalid_json(self):
        response = frontik_test_app.get_page('json_page?invalid=true', notpl=True)
        assert response.headers['content-type'].startswith('application/json') is True

        data = json.loads(response.content)
        assert data['req1']['result'] == '1'
        assert data['req2']['error']['reason'] == 'invalid json'

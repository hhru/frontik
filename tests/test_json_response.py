import json
import unittest

from .instances import frontik_test_app


class TestJsonResponse(unittest.TestCase):
    def test_json(self):
        response = frontik_test_app.get_page('json_page', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/json'))

        data = json.loads(response.content)
        self.assertEqual(data['req1']['result'], '1')
        self.assertEqual(data['req2']['result'], '2')

    def test_invalid_json(self):
        response = frontik_test_app.get_page('json_page?invalid=true', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/json'))

        data = json.loads(response.content)
        self.assertEqual(data['req1']['result'], '1')
        self.assertEqual(data['req2']['error']['reason'], 'invalid json')

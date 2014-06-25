# coding=utf-8

import json
import unittest

from tests.instances import frontik_debug


class TestJsonResponse(unittest.TestCase):
    def test_json(self):
        response = frontik_debug.get_page('test_app/json_page', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/json'))

        data = json.loads(response.content)
        self.assertEqual(data['req1']['result'], '1')
        self.assertEqual(data['req2']['result'], '2')

    def test_invalid_json(self):
        response = frontik_debug.get_page('test_app/json_page?invalid=true', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/json'))

        data = json.loads(response.content)
        self.assertEqual(data['req1']['result'], '1')
        self.assertEqual(data['req2']['error']['reason'], 'invalid JSON')

    def test_jinja(self):
        response = frontik_debug.get_page('test_app/json_page')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, '<html><body><b>1</b><i>2</i></body></html>')

# coding=utf-8

import json
import unittest

from tests import frontik_debug


class TestJsonResponse(unittest.TestCase):
    def test_json(self):
        with frontik_debug.get_page('test_app/json_page', notpl=True) as response:
            self.assertTrue(response.headers['content-type'].startswith('application/json'))

            data = json.loads(response.read())
            self.assertEqual(data['req1']['result'], '1')
            self.assertEqual(data['req2']['result'], '2')

    def test_jinja(self):
        with frontik_debug.get_page('test_app/json_page') as response:
            self.assertTrue(response.headers['content-type'].startswith('text/html'))

            data = response.read()
            self.assertEqual(data, '<html><body><b>1</b><i>2</i></body></html>')

import json
import unittest

from .instances import frontik_test_app


class TestJsonResponse(unittest.TestCase):
    def test_validation(self):
        response = frontik_test_app.get_page('validate_arguments?list=1&list=2&string=safestring', notpl=True)

        data = json.loads(response.content)
        self.assertEqual(data['list'], [1, 2])
        self.assertEqual(data['string'], 'safestring')

    def test_validation_failed(self):
        response = frontik_test_app.get_page('validate_arguments?list=1&list=2&string=un/safe', notpl=True)

        self.assertEqual(response.status_code, 400)

import json
import unittest

from .instances import frontik_test_app


class TestJsonResponse(unittest.TestCase):
    def test_validation(self):
        response = frontik_test_app.get_page('validate_arguments?list=1&list=2&string=safestring', notpl=True)

        data = json.loads(response.content)
        self.assertEqual([1, 2], data['list'])
        self.assertEqual('safestring', data['string'])

    def test_validation_failed(self):
        response = frontik_test_app.get_page('validate_arguments?list=1&list=2&string=un/safe', notpl=True)

        self.assertEqual(response.status_code, 400)

    def test_validation_model(self):
        response = frontik_test_app.get_page('validate_arguments?list=1&list=2&string=nword&model=true', notpl=True)

        data = json.loads(response.content)
        self.assertEqual([1, 2], data['list'])
        self.assertEqual('customString', data['string'])

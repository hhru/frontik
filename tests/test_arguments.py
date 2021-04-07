import unittest
from urllib.parse import urlencode

import requests

from .instances import frontik_test_app


class TestJsonResponse(unittest.TestCase):

    def setUp(self) -> None:
        self.query_args = {
            'list': [1, 2],
            'string': 'safestring',
            'str_arg': '',
            'int_arg_with_default': '',
            'int_arg': '',
        }
        return super().setUp()

    def test_validation(self):

        self.query_args.update(int_arg=0)
        get_data = frontik_test_app.get_page_json(
            f'validate_arguments?{urlencode(self.query_args, doseq=True)}',
            notpl=True
        )

        self.assertEqual([1, 2], get_data['list'])
        self.assertEqual('safestring', get_data['string'])
        self.assertEqual('', get_data['str_arg'])
        self.assertEqual('default', get_data['str_arg_with_default'])
        self.assertEqual(0, get_data['int_arg_with_default'])

        post_data = frontik_test_app.get_page_json(
            'validate_arguments',
            notpl=True,
            method=requests.post,
            data=self.query_args,
        )
        self.assertEqual('default', post_data['str_body_arg'])
        self.assertEqual(0, post_data['int_body_arg'])

    def test_validation_failed(self):
        self.query_args.update(string='un/safe')
        response = frontik_test_app.get_page(f'validate_arguments?{urlencode(self.query_args, doseq=True)}', notpl=True)

        self.assertEqual(response.status_code, 400)

    def test_arg_validation_raises_for_empty_value_with_no_default(self):
        response = frontik_test_app.get_page(f'validate_arguments?{urlencode(self.query_args, doseq=True)}', notpl=True)

        self.assertEqual(response.status_code, 400)

    def test_arg_validation_raises_for_default_of_incorrect_type(self):
        response = frontik_test_app.get_page('validate_arguments?str_arg=test', method=requests.put, notpl=True)

        self.assertEqual(response.status_code, 500)

    def test_validation_model(self):
        self.query_args.update(int_arg=0)
        self.query_args.update(model=True)

        data = frontik_test_app.get_page_json(
            f'validate_arguments?{urlencode(self.query_args, doseq=True)}',
            notpl=True
        )

        self.assertEqual([1, 2], data['list'])
        self.assertEqual('customString', data['string'])

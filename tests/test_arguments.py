from urllib.parse import urlencode

import requests

from tests.instances import frontik_test_app


class TestJsonResponse:

    def setup_method(self):
        self.query_args = {
            'list': [1, 2],
            'string': 'safestring',
            'str_arg': '',
            'int_arg_with_default': '',
            'int_arg': '',
        }

    def test_validation(self):

        self.query_args.update(int_arg=0)
        get_data = frontik_test_app.get_page_json(
            f'validate_arguments?{urlencode(self.query_args, doseq=True)}',
            notpl=True
        )

        assert get_data['list'] == [1, 2]
        assert get_data['string'] == 'safestring'
        assert get_data['str_arg'] == ''
        assert get_data['str_arg_with_default'] == 'default'
        assert get_data['int_arg_with_default'] == 0
        assert get_data['none_float'] is True

        post_data = frontik_test_app.get_page_json(
            'validate_arguments',
            notpl=True,
            method=requests.post,
            data=self.query_args,
        )
        assert post_data['str_body_arg'] == 'default'
        assert post_data['int_body_arg'] == 0

    def test_validation_failed(self):
        self.query_args.update(string='un/safe')
        response = frontik_test_app.get_page(f'validate_arguments?{urlencode(self.query_args, doseq=True)}', notpl=True)

        assert response.status_code == 400

    def test_arg_validation_raises_for_empty_value_with_no_default(self):
        response = frontik_test_app.get_page(f'validate_arguments?{urlencode(self.query_args, doseq=True)}', notpl=True)

        assert response.status_code == 400

    def test_arg_validation_raises_for_default_of_incorrect_type(self):
        response = frontik_test_app.get_page('validate_arguments?str_arg=test', method=requests.put, notpl=True)

        assert response.status_code == 500

    def test_validation_model(self):
        self.query_args.update(int_arg=0)
        self.query_args.update(model=True)

        data = frontik_test_app.get_page_json(
            f'validate_arguments?{urlencode(self.query_args, doseq=True)}',
            notpl=True
        )

        assert data['list'] == [1, 2]
        assert data['string'] == 'customString'

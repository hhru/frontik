from typing import Optional

from frontik.handler import PageHandler
from frontik.validator import BaseValidationModel, Validators
from pydantic import validator


class CustomModel(BaseValidationModel):
    string: Optional[str]

    @validator('string')
    @classmethod
    def check_string(cls, value):
        assert 'someword' not in value
        return 'customString'


class Page(PageHandler):
    def get_page(self):
        is_custom_model = self.get_bool_argument('model', False)
        empty_default_str = self.get_str_argument('str_arg_with_default', 'default')
        empty_default_int = self.get_int_argument('int_arg_with_default', 0)
        empty_str = self.get_str_argument('str_arg')
        self.get_int_argument('int_arg')

        if is_custom_model:
            self.set_validation_model(CustomModel)

        list_int = self.get_validated_argument('list', Validators.LIST_INT, array=True)
        string = self.get_str_argument('string', path_safe=not is_custom_model)

        self.json.put({
            'list': list_int,
            'string': string,
            'str_arg_with_default': empty_default_str,
            'int_arg_with_default': empty_default_int,
            'str_arg': empty_str,
        })

    def post_page(self):
        str_body_arg = self.get_str_argument('str_argument', 'default', from_body=True)
        int_body_arg = self.get_int_argument('int_argument', 0, from_body=True)

        self.json.put({
            'str_body_arg': str_body_arg,
            'int_body_arg': int_body_arg,
        })

    def put_page(self):
        self.get_str_argument('str_arg', 3)

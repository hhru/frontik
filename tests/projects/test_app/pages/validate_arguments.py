from typing import Optional

from pydantic import field_validator

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from frontik.validator import BaseValidationModel, Validators


class CustomModel(BaseValidationModel):
    string: Optional[str] = None

    @field_validator('string')
    @classmethod
    def check_string(cls, value):
        assert 'someword' not in value
        return 'customString'


@router.get('/validate_arguments', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    is_custom_model = handler.get_bool_argument('model', False)
    empty_default_str = handler.get_str_argument('str_arg_with_default', 'default')
    empty_default_int = handler.get_int_argument('int_arg_with_default', 0)
    empty_str = handler.get_str_argument('str_arg')
    none_float = handler.get_float_argument('test', None)
    handler.get_int_argument('int_arg')

    if is_custom_model:
        handler.set_validation_model(CustomModel)

    list_int = handler.get_validated_argument('list', Validators.LIST_INT, array=True)
    string = handler.get_str_argument('string', path_safe=not is_custom_model)

    handler.json.put({
        'list': list_int,
        'string': string,
        'str_arg_with_default': empty_default_str,
        'int_arg_with_default': empty_default_int,
        'str_arg': empty_str,
        'none_float': none_float is None,
    })


@router.post('/validate_arguments', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    str_body_arg = handler.get_str_argument('str_argument', 'default', from_body=True)
    int_body_arg = handler.get_int_argument('int_argument', 0, from_body=True)

    handler.json.put({'str_body_arg': str_body_arg, 'int_body_arg': int_body_arg})


@router.put('/validate_arguments', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.get_str_argument('str_arg', 3)

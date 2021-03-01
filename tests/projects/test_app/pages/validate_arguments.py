from pydantic import validator
from typing import Optional

from frontik.handler import PageHandler
from frontik.validator import Validators, BaseValidationModel


class CustomModel(BaseValidationModel):
    string: Optional[str]

    @validator('string')
    @classmethod
    def check_string(cls, value):
        assert 'someword' not in value
        return 'customString'


class Page(PageHandler):
    def get_page(self):
        is_custom_model = self.get_boolean_argument('model', False)

        if is_custom_model:
            self.set_validation_model(CustomModel)

        list_int = self.get_validated_argument('list', Validators.LIST_INT, array=True)
        string = self.get_string_argument('string', path_safe=not is_custom_model)

        self.json.put({'list': list_int, 'string': string})

from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class Validators(Enum):
    BOOLEAN = 'boolean'
    STRING = 'string'
    INTEGER = 'integer'
    FLOAT = 'float_'
    LIST_INT = 'list_int'
    LIST_STR = 'list_str'
    PATH_SAFE_STRING = 'path_safe_string'


class BaseValidationModel(BaseModel):
    boolean: Optional[bool] = None
    string: Optional[str] = None
    integer: Optional[int] = None
    float_: Optional[float] = None
    list_int: Optional[list[int]] = None
    list_str: Optional[list[str]] = None
    path_safe_string: Optional[str] = None

    @field_validator('path_safe_string', mode='before')
    @classmethod
    def check_path_safe_string(cls, value):
        assert isinstance(value, str)
        assert '/' not in value
        return value

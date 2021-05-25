from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, validator


class Validators(Enum):
    BOOLEAN = 'boolean'
    STRING = 'string'
    INTEGER = 'integer'
    FLOAT = 'float'
    LIST_INT = 'list_int'
    LIST_STR = 'list_str'
    PATH_SAFE_STRING = 'path_safe_string'


class BaseValidationModel(BaseModel):
    boolean: Optional[bool]
    string: Optional[str]
    integer: Optional[int]
    float: Optional[float]
    list_int: Optional[List[int]]
    list_str: Optional[List[str]]
    path_safe_string: Optional[str]

    @validator('path_safe_string', pre=True)
    @classmethod
    def check_path_safe_string(cls, value):
        assert isinstance(value, str) and '/' not in value
        return value

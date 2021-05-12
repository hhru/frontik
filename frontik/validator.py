import re

from enum import Enum
from typing import List, Optional,Pattern

from pydantic import BaseModel, validator

HASH_REGEXP: Pattern = re.compile(r"^[a-f0-9]{6,128}$", re.IGNORECASE)


class Validators(Enum):
    BOOLEAN = 'boolean'
    STRING = 'string'
    INTEGER = 'integer'
    FLOAT = 'float'
    LIST_INT = 'list_int'
    LIST_STR = 'list_str'
    PATH_SAFE_STRING = 'path_safe_string'
    HASH_STRING = 'hash_string'


class BaseValidationModel(BaseModel):
    boolean: Optional[bool]
    string: Optional[str]
    integer: Optional[int]
    float: Optional[float]
    list_int: Optional[List[int]]
    list_str: Optional[List[str]]
    path_safe_string: Optional[str]
    hash_string: Optional[str]

    @validator('path_safe_string')
    @classmethod
    def check_path_safe_string(cls, value):
        assert '/' not in value
        return value


    @validator('hash_string')
    @classmethod
    def check_hash_string(cls, value):
        check_string = None
        if isinstance(value, str):
            check_string = HASH_REGEXP.fullmatch(value)
        
        assert check_string is not None and check_string.group(0) == value
        return value

from enum import Enum

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
    boolean: bool | None
    string: str | None
    integer: int | None
    float: float | None
    list_int: list[int] | None
    list_str: list[str] | None
    path_safe_string: str | None

    @validator('path_safe_string', pre=True)
    @classmethod
    def check_path_safe_string(cls, value):
        assert isinstance(value, str)
        assert '/' not in value
        return value

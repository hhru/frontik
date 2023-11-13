from enum import Enum

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
    boolean: bool | None = None
    string: str | None = None
    integer: int | None = None
    float_: float | None = None
    list_int: list[int] | None = None
    list_str: list[str] | None = None
    path_safe_string: str | None = None

    @field_validator('path_safe_string', mode='before')
    @classmethod
    def check_path_safe_string(cls, value):
        assert isinstance(value, str)
        assert '/' not in value
        return value

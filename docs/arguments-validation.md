## Argument validation
To get arguments validated by type hints or specific validators you should use page handler method named `get_validated_argument`
which is a wrapper for such methods as [`get_argument`, `get_arguments`, `get_body_argument`, `get_body_arguments`].

Following logic applies for validation:
- if default value is of incorrect type as specified by `validation` arg, then `DefaultValueError` will be raised, **even if valid value is present in request args**
- `get_validated_argument` returns default value if argument value is invalid
- if no default value is present then `HTTPErrorWithPostprocessors(http.client.BAD_REQUEST)` will be raised



```
get_validated_argument(name, validation, default, from_body, array, strip) -> Any
```
* name `[str][required]` - name of argument
* validation [ [Validators](https://github.com/hhru/frontik/blob/master/frontik/validator.py#L7) ] `[required]` - name of used validator (field of Enum)
* default `[any]` - must conform validator specified, passed further as tornado `get_argument/get_arguments/get_body_argument/get_body_arguments` param
* from_body `[bool][default=False]` - flag for getting arguments from response body
* array `[bool][default=False]` - flag for getting many arguments (i.g. like `get_arguments`)
* strip `[bool][default=True]` - passed further as tornado `get_argument/get_body_argument` param

`get_validated argument` uses [BaseValidationModel](https://github.com/hhru/frontik/blob/master/frontik/validator.py#L17)
as default model for validation.
You can use custom validation model which inherited from `BaseValidationModel` or [BaseModel](https://pydantic-docs.helpmanual.io/usage/models/#basic-model-usage).
More about custom validators you can read [here](https://pydantic-docs.helpmanual.io/usage/validators/).

To set custom validation Model for the lifetime of Handler instance you should use method `set_validation_model`.
```
set_validation_model(model)
```
* model `Type[Union[BaseValidationModel, BaseModel]][required]` - validation model (class) that inherited from `BaseValidationModel` or `BaseModel` (pydantic)

For example:
```python
class CustomValidationModel(BaseModel):
    custom_int: int
    custom_arg: Optional[int]

    @validator('custom_arg')
    @classmethod
    def validate_custom_arg(cls, value):
        assert value % 5 == 0
        return value

def get_page(self):
    self.set_validation_model(CustomValidationModel)
```


For shortening usage of `get_validated_argument` for specific types you can use next methods
(all of these methods will pass `*args` `**kwargs` to original `get_validated_argument`):

Get string argument:
```
get_str_argument(name, path_safe) -> Union[str, List[str]]
```
* path_safe`[bool][default=True]` - flag to use validator which detects dangerous symbols to pass to path

Get int argument:
```
get_int_argument(name) -> Union[int, List[int]]
```

Get bool argument:
```
get_bool_argument(name) -> Union[bool, List[bool]]
```

Get float argument:
```
get_float_argument(name) -> Union[float, List[float]]
```

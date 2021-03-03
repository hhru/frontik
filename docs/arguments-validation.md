## Argument validation
To get arguments validated by type hints or specific validators you should use
page handler method named `get_validated_argument`

```
get_validated_argument(name, validation, default, from_body, array, strip) -> any
```
* name `[str][required]` - name of argument
* validation `[Validators][required]` - name of used validator (field of Enum)
* default `[any]` - default value for argument in case it's not found
* from_body `[bool][default=False]` - flag for getting arguments from response body
* array `[bool][default=False]` - flag for getting many arguments (i.g. like `get_arguments`)
* strip `[bool][default=True]` - flag for stripping argument value

`get_validated argument` uses `BaseValidationModel` as default model for validation.
You can use custom validation model which inherited from `BaseValidationModel` or `BaseModel` (pydantic).
To do this you should use method `set_validation_model`.
```
set_validation_model(model)
```
* model `Type[Union[BaseValidationModel, BaseModel]][required]` - validation model (class) that inherited from `BaseValidationModel` or `BaseModel` (pydantic)

For shortening usage of `get_validated_argument` for specific types you can use next methods
(all of these methods will pass `*args` `**kwargs` to original `get_validated_argument`):

Get string argument:
```
get_string_argument(name, path_safe) -> Optional[str]
```
* path_safe`[bool][default=True]` - flag to use validator which detects dangerous symbols to pass to path

Get int argument: 
```
get_integer_argument(name) -> Optional[int]
```

Get bool argument:
```
get_boolean_argument(name) -> Optional[bool]
```
 
Get float argument:
```
get_float_argument(name) -> Optional[float]
``` 

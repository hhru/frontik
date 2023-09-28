from __future__ import annotations
import asyncio
from functools import wraps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Reversible


def _get_preprocessor_name(preprocessor_function: Any) -> str:
    return f'{preprocessor_function.__module__}.{preprocessor_function.__name__}'


def preprocessor(function_or_list: Callable|Reversible[Callable]) -> Callable:
    """Creates a preprocessor decorator for `PageHandler.get_page`, `PageHandler.post_page` etc.

    Preprocessor is a function that accepts handler instance as its only parameter.
    Preprocessor can return a ``Future`` (any other value is ignored) and is considered
    finished when this ``Future`` is resolved.

    Several ``@preprocessor`` decorators are executed sequentially.

    Usage::
        @preprocessor
        def get_a(handler):
            future = Future()
            # Do something asynchronously
            yield future

        @preprocessor
        def get_b(handler):
            # Do something
            return None

        class Page(PageHandler):
            @get_a
            @get_b
            # Can also be rewritten as:
            # @preprocessor([get_a, get_b])
            def get_page(self):
                pass

    When the ``Future`` returned by ``get_a`` is resolved, ``get_b`` is called.
    Finally, after ``get_b`` is executed, ``get_page`` will be called.
    """

    def preprocessor_decorator(func: Callable) -> Callable:
        if callable(function_or_list):
            _register_preprocessors(func, [function_or_list])
        else:
            for dep in reversed(function_or_list):
                dep(func)

        return func

    if callable(function_or_list):
        dep_name = function_or_list.__name__
        preprocessor_decorator.preprocessor_name = _get_preprocessor_name(function_or_list)  # type: ignore
        preprocessor_decorator.function = function_or_list  # type: ignore
    else:
        dep_name = str([f.__name__ for f in function_or_list])
    preprocessor_decorator.func_name = f'preprocessor_decorator({dep_name})'  # type: ignore

    return preprocessor_decorator


def _get_preprocessors(func: Callable) -> list:
    return getattr(func, '_preprocessors', [])


def _unwrap_preprocessors(preprocessors: Reversible) -> list:
    return _get_preprocessors(preprocessor(preprocessors)(lambda: None))


def _register_preprocessors(func: Callable, preprocessors: list[Callable]) -> None:
    setattr(func, '_preprocessors', preprocessors + _get_preprocessors(func))


def make_preprocessors_names_list(preprocessors_list: list) -> list[str]:
    return list(map(lambda p: p.preprocessor_name, preprocessors_list))


def _wrap_async_func_to_tornado_coroutine(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.create_task(func(*args, **kwargs))

    wrapper.__wrapped__ = func  # type: ignore
    wrapper.__tornado_coroutine__ = True  # type: ignore

    return wrapper

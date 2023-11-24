from collections.abc import Callable
from typing import Any


class Preprocessor:
    """Deprecated, use frontik.dependency_manager.Dependency"""

    def __init__(self, preprocessor_function: Callable) -> None:
        self.preprocessor_function = preprocessor_function

    @property
    def preprocessor_name(self) -> str:
        return make_full_name(self.preprocessor_function)

    def __call__(self, page_func: Callable) -> Callable:
        setattr(page_func, '_preprocessors', [*get_preprocessors(page_func), self.preprocessor_function])
        return page_func


def preprocessor(preprocessor_function: Callable) -> Preprocessor:
    """Deprecated, use frontik.dependency_manager.Dependency"""
    return Preprocessor(preprocessor_function)


def get_preprocessors(func: Callable) -> list:
    return getattr(func, '_preprocessors', [])


def make_full_name(func: Callable | Any) -> str:
    return f'{func.__module__}.{func.__name__}'

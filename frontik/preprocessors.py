from collections.abc import Callable, Generator
from typing import Any


class DependencyGroupMarker:
    __name__ = 'dep_group'

    def __init__(self, deps: list[Callable]) -> None:
        self.deps = deps


class Preprocessor:
    """Deprecated, use frontik.dependency_manager.Dependency"""

    def __init__(self, preprocessor_function: Callable | DependencyGroupMarker) -> None:
        self.preprocessor_function = preprocessor_function

    @property
    def preprocessor_name(self) -> str:
        return make_full_name(self.preprocessor_function)

    def __call__(self, page_func: Callable) -> Callable:
        setattr(page_func, '_preprocessors', [*get_preprocessors(page_func), self.preprocessor_function])
        return page_func


def preprocessor(preprocessor_function: Callable | DependencyGroupMarker) -> Preprocessor:
    """Deprecated, use frontik.dependency_manager.Dependency"""
    return Preprocessor(preprocessor_function)


def get_preprocessors(func: Callable) -> list:
    return getattr(func, '_preprocessors', [])


def get_simple_preprocessors_functions(func: Callable) -> Generator:
    for preproc in getattr(func, '_preprocessors', []):
        if not isinstance(preproc, DependencyGroupMarker):
            yield preproc


def get_all_preprocessors_functions(func: Callable) -> Generator:
    for preproc in getattr(func, '_preprocessors', []):
        if isinstance(preproc, DependencyGroupMarker):
            for func_or_preproc in preproc.deps:
                if isinstance(func_or_preproc, Preprocessor):
                    yield func_or_preproc.preprocessor_function
                else:
                    yield func_or_preproc
        else:
            yield preproc


def make_preprocessors_names_list(preprocessors_list: list) -> list[str]:
    return [p.preprocessor_name if isinstance(p, Preprocessor) else make_full_name(p) for p in preprocessors_list]


def make_full_name(func: Callable | Any) -> str:
    return f'{func.__module__}.{func.__name__}'

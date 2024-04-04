import logging
from fastapi.routing import APIRouter
from typing import Callable
import re
import inspect
import importlib
import pkgutil


routing_logger = logging.getLogger('frontik.routing')

routers = []
normal_routes = {}
regex_mapping = []


class FrontikRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        routers.append(self)
        self._cls = None
        self._path = None

    def get(self, path: str, cls, **kwargs) -> Callable:
        self._path, self._cls = path, cls
        return super().get(path, **kwargs)

    def post(self, path: str, cls, **kwargs) -> Callable:
        self._path, self._cls = path, cls
        return super().post(path, **kwargs)

    def put(self, path: str, cls, **kwargs) -> Callable:
        self._path, self._cls = path, cls
        return super().put(path, **kwargs)

    def delete(self, path: str, cls, **kwargs) -> Callable:
        self._path, self._cls = path, cls
        return super().delete(path, **kwargs)

    def add_api_route(self, *args, **kwargs):
        super().add_api_route(*args, **kwargs)
        route = self.routes[-1]
        m = next(iter(route.methods), None)
        normal_routes[(self._path, m)] = (route, self._cls)  # нам нужен дикт роутов, чтобы знать класс хендлера
        self._cls, self._path = None, None


class FrontikRegexRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        routers.append(self)
        self._cls = None
        self._path = None

    def get(self, path: str, cls, **kwargs) -> Callable:
        self._path, self._cls = path, cls
        return super().get(path, **kwargs)

    def post(self, path: str, cls, **kwargs) -> Callable:
        self._path, self._cls = path, cls
        return super().post(path, **kwargs)

    def put(self, path: str, cls, **kwargs) -> Callable:
        self._path, self._cls = path, cls
        return super().put(path, **kwargs)

    def delete(self, path: str, cls, **kwargs) -> Callable:
        self._path, self._cls = path, cls
        return super().delete(path, **kwargs)

    def add_api_route(self, *args, **kwargs):
        super().add_api_route(*args, **kwargs)

        regex_mapping.append((
            re.compile(self._path),
            self.routes[-1],
            self._cls
        ))

        self._cls, self._path = None, None


def build_path() -> str:
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    page_file_path = calframe[1].filename
    idx = page_file_path.find('/pages')
    if idx == -1:
        raise RuntimeError('cant generate url path')

    return page_file_path[idx + 6:-3]


def _import_submodules(package: str) -> None:
    package = importlib.import_module(package)
    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + '.' + name
        try:
            importlib.import_module(full_name)
        except ModuleNotFoundError:
            continue
        except Exception as ex:
            routing_logger.error('failed on import page %s %s', full_name, ex)
            continue
        if is_pkg:
            _import_submodules(full_name)


def fill_router(app_module: str) -> None:
    # import all pages on startup
    package_name = f'{app_module}.pages'
    _import_submodules(package_name)

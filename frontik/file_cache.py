import copy
import logging
import os
from collections.abc import Callable
from typing import Any, Optional, Union

from frontik.options import options


# This implementation is broken in so many ways
class LimitedDict(dict):
    def __init__(self, max_len: Optional[int] = None, step: Optional[int] = None, deepcopy: bool = False) -> None:
        dict.__init__(self)
        self._order: list = []
        self.max_len = max_len
        self.step = step
        self.deepcopy = deepcopy

    def __getitem__(self, key):
        val = dict.__getitem__(self, key)
        if self.max_len is not None:
            if self.step:
                ind = self._order.index(key)
                self._order.remove(key)
                self._order.insert(ind + self.step, key)
            else:
                self._order.remove(key)
                self._order.append(key)
        return copy.deepcopy(val) if self.deepcopy else val

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        if self.max_len is not None:
            if self.step:
                self._order.insert(self.step, key)
            else:
                self._order.append(key)
        if self.max_len is not None and len(self._order) > self.max_len:
            self.pop(self._order.pop(0))


class FileCache:
    """
    load_fn :: filename -> (status, result)
    """

    def __init__(
        self,
        cache_name: str,
        root_dir: str,
        load_fn: Callable,
        max_len: Optional[int] = None,
        step: Optional[int] = None,
        deepcopy: bool = False,
    ) -> None:
        self.cache_name = cache_name
        self.root_dir = root_dir
        self.load_fn = load_fn
        self.frozen = False
        self.max_len = max_len
        self.cache = LimitedDict(max_len, step, deepcopy)

    def populate(self, filenames: list, log: logging.Logger, freeze: bool = False) -> None:
        if self.max_len == 0:
            return

        for filename in filenames:
            self._load(filename, log)

        self.frozen = freeze and self.max_len is None

    def load(self, filename: str, log: logging.Logger) -> Any:
        if filename in self.cache:
            log.debug('got %s file from cache (%s cache size: %s)', filename, self.cache_name, len(self.cache))
            return self.cache[filename]

        if self.frozen:
            msg = f'encounter file {filename} not in cache while cache is frozen'
            raise Exception(msg)

        return self._load(filename, log)

    def _load(self, filename: str, log: logging.Logger) -> Any:
        real_filename = os.path.normpath(os.path.join(self.root_dir, filename))
        log.info('reading file "%s"', real_filename)
        result = self.load_fn(real_filename, log)
        self.cache[filename] = result

        return result


class InvalidOptionCache:
    def __init__(self, option: str) -> None:
        self.option = option

    def load(self, filename, *args, **kwargs):
        msg = f'{self.option} option is undefined'
        raise Exception(msg)


def make_file_cache(
    cache_name: str,
    option_name: str,
    root_dir: Optional[str],
    fun: Callable,
    max_len: Optional[int] = None,
    step: Optional[int] = None,
    deepcopy: bool = False,
) -> Union[FileCache, InvalidOptionCache]:
    if root_dir:
        # disable cache in development environment
        max_len = 0 if options.debug else max_len
        return FileCache(cache_name, root_dir, fun, max_len, step, deepcopy)
    else:
        return InvalidOptionCache(option_name)

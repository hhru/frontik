import abc
from collections import namedtuple

LogLevelOverride = namedtuple('LogLevelOverride', ['logger_name', 'log_level'])


class LogLevelOverrideExtension(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def load_log_level_overrides(self) -> list[LogLevelOverride]:
        pass

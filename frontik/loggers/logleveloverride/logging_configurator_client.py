from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING

from tornado.ioloop import PeriodicCallback

from frontik.options import options

if TYPE_CHECKING:
    from collections.abc import Iterable

    from frontik.loggers.logleveloverride.log_level_override_extension import LogLevelOverrideExtension

LOG_LEVEL_MAPPING = {
    'TRACE': logging.DEBUG,
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARN': logging.WARNING,
    'ERROR': logging.ERROR,
}


class LoggingConfiguratorClient:
    def __init__(self, log_level_override_extension: LogLevelOverrideExtension):
        self.log_level_override_extension = log_level_override_extension
        self._loggers_store: dict[str, int] = {}
        self._update_task_handle = PeriodicCallback(
            callback=self._update_log_level,
            callback_time=options.update_log_level_interval_in_seconds * 1000,
        )

        self._update_task_handle.start()

    async def _update_log_level(self) -> None:
        log_level_overrides = await self.log_level_override_extension.load_log_level_overrides()
        self._rollback_overrides(log_level_overrides)
        for logger_name, log_level in log_level_overrides:
            if self._loggers_store.get(logger_name, None) == log_level:
                continue

            logger = logging.getLogger(logger_name)
            logger.setLevel(log_level)

            if logger.handlers:
                for handler in logger.handlers:
                    handler.setLevel(log_level)
            else:
                for handler in logging.getLogger().handlers:
                    parent_handler_copy = copy.copy(handler)
                    parent_handler_copy.setLevel(log_level)
                    logger.addHandler(parent_handler_copy)

            self._loggers_store[logger.name] = logger.level

    def _rollback_overrides(self, overrides: Iterable = ()) -> None:
        for logger_name in self._loggers_store.keys() - {x.logger_name for x in overrides}:
            del self._loggers_store[logger_name]
            self._reset_log_level(logger_name)

    def _reset_log_level(self, logger_name: str) -> None:
        logger = logging.getLogger(logger_name)
        logger.setLevel(options.log_level.upper())
        for handler in logger.handlers:
            handler.setLevel(options.log_level.upper())

    def stop_logging_configurator(self) -> None:
        self._update_task_handle.stop()

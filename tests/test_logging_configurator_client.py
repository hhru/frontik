import logging
import unittest
from typing import List

import pytest as pytest
from tornado import options
from tornado.options import define

from frontik.loggers.logleveloverride.log_level_override_extension import LogLevelOverrideExtension, LogLevelOverride
from frontik.loggers.logleveloverride.logging_configurator_client import LoggingConfiguratorClient

MOCK_LOG_OVERRIDE_DTO = [
    LogLevelOverride('a', 'DEBUG'),
    LogLevelOverride('b', 'INFO'),
    LogLevelOverride('c', 'WARN'),
]


class TestLogLevelOverrideExtension(LogLevelOverrideExtension):

    async def load_log_level_overrides(self) -> List[LogLevelOverride]:
        return MOCK_LOG_OVERRIDE_DTO


class TestLoggingConfiguratorClient(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if 'update_log_level_interval_in_seconds' not in options.options:
            define('update_log_level_interval_in_seconds', default=1, type=int)
        if 'log_level' not in options.options:
            define('log_level', default='info', type=str)

    def setUp(self) -> None:
        self.logging_configurator_client = LoggingConfiguratorClient(TestLogLevelOverrideExtension())
        self.logging_configurator_client.stop_logging_configurator()
        logging.getLogger().handlers.clear()
        logging.getLogger('a').handlers.clear()
        logging.getLogger('b').handlers.clear()
        logging.getLogger('c').handlers.clear()

    def tearDown(self) -> None:
        MOCK_LOG_OVERRIDE_DTO.append(LogLevelOverride('a', 'DEBUG'))
        MOCK_LOG_OVERRIDE_DTO.append(LogLevelOverride('b', 'INFO'))
        MOCK_LOG_OVERRIDE_DTO.append(LogLevelOverride('c', 'WARN'))

    @pytest.mark.asyncio
    async def test_simple_override(self):
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(len(self.logging_configurator_client._loggers_store), 3)

    @pytest.mark.asyncio
    async def test_override_and_remove(self):
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(len(self.logging_configurator_client._loggers_store), 3)

        MOCK_LOG_OVERRIDE_DTO.clear()

        await self.logging_configurator_client._update_log_level()
        self.assertEqual(len(self.logging_configurator_client._loggers_store), 0)

    @pytest.mark.asyncio
    async def test_override_and_after_change_level(self):
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(logging.getLogger('a').level, logging.DEBUG)

        MOCK_LOG_OVERRIDE_DTO.clear()

        MOCK_LOG_OVERRIDE_DTO.append(LogLevelOverride('a', 'INFO'))
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(logging.getLogger('a').level, logging.INFO)

    @pytest.mark.asyncio
    async def test_level_with_handlers(self):
        logging.getLogger().handlers.append(logging.Handler())
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(logging.getLogger('a').level, logging.DEBUG)
        self.assertEqual(logging.getLogger('a').handlers[0].level, logging.DEBUG)
        self.assertEqual(logging.getLogger('b').handlers[0].level, logging.INFO)
        self.assertEqual(logging.getLogger('c').handlers[0].level, logging.WARN)

        MOCK_LOG_OVERRIDE_DTO.clear()

        MOCK_LOG_OVERRIDE_DTO.append(LogLevelOverride('a', 'INFO'))
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(logging.getLogger('a').level, logging.INFO)
        self.assertEqual(len(logging.getLogger('a').handlers), 1)
        self.assertEqual(logging.getLogger('a').handlers[0].level, logging.INFO)
        self.assertEqual(logging.getLogger('b').handlers[0].level, logging.INFO)
        self.assertEqual(logging.getLogger('c').handlers[0].level, logging.INFO)

    @pytest.mark.asyncio
    async def test_not_add_root_handlers_if_exist_on_specific_logger(self):
        logging.getLogger().handlers.append(logging.Handler())
        logging.getLogger().handlers.append(logging.Handler())
        logging.getLogger('a').handlers.append(logging.Handler())

        await self.logging_configurator_client._update_log_level()
        self.assertEqual(len(logging.getLogger('a').handlers), 1)
        self.assertEqual(len(logging.getLogger('b').handlers), 2)
        self.assertEqual(len(logging.getLogger('c').handlers), 2)
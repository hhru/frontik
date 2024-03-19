import logging
import unittest

import pytest as pytest

from frontik.loggers.logleveloverride.log_level_override_extension import LogLevelOverride, LogLevelOverrideExtension
from frontik.loggers.logleveloverride.logging_configurator_client import LoggingConfiguratorClient

MOCK_LOG_OVERRIDE_DTO = [LogLevelOverride('a', 'DEBUG'), LogLevelOverride('b', 'INFO'), LogLevelOverride('c', 'WARN')]


class TestLogLevelOverrideExtension(LogLevelOverrideExtension):
    async def load_log_level_overrides(self) -> list[LogLevelOverride]:
        return MOCK_LOG_OVERRIDE_DTO


class TestLoggingConfiguratorClient(unittest.TestCase):
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

    @pytest.mark.asyncio()
    async def test_simple_override(self):
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(len(self.logging_configurator_client._loggers_store), 3)

    @pytest.mark.asyncio()
    async def test_override_and_remove(self):
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(len(self.logging_configurator_client._loggers_store), 3)

        MOCK_LOG_OVERRIDE_DTO.clear()

        await self.logging_configurator_client._update_log_level()
        self.assertEqual(len(self.logging_configurator_client._loggers_store), 0)

    @pytest.mark.asyncio()
    async def test_override_and_after_change_level(self):
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(logging.getLogger('a').level, logging.DEBUG)

        MOCK_LOG_OVERRIDE_DTO.clear()

        MOCK_LOG_OVERRIDE_DTO.append(LogLevelOverride('a', 'INFO'))
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(logging.getLogger('a').level, logging.INFO)

    @pytest.mark.asyncio()
    async def test_level_with_handlers(self):
        logging.getLogger().handlers.append(logging.Handler())
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(logging.getLogger('a').level, logging.DEBUG)
        self.assertEqual(logging.getLogger('a').handlers[0].level, logging.DEBUG)
        self.assertEqual(logging.getLogger('b').handlers[0].level, logging.INFO)
        self.assertEqual(logging.getLogger('c').handlers[0].level, logging.WARNING)

        MOCK_LOG_OVERRIDE_DTO.clear()

        MOCK_LOG_OVERRIDE_DTO.append(LogLevelOverride('a', 'INFO'))
        await self.logging_configurator_client._update_log_level()
        self.assertEqual(logging.getLogger('a').level, logging.INFO)
        self.assertEqual(len(logging.getLogger('a').handlers), 1)
        self.assertEqual(logging.getLogger('a').handlers[0].level, logging.INFO)
        self.assertEqual(logging.getLogger('b').handlers[0].level, logging.INFO)
        self.assertEqual(logging.getLogger('c').handlers[0].level, logging.INFO)

    @pytest.mark.asyncio()
    async def test_not_add_root_handlers_if_exist_on_specific_logger(self):
        logging.getLogger().handlers.append(logging.Handler())
        logging.getLogger().handlers.append(logging.Handler())
        logging.getLogger('a').handlers.append(logging.Handler())

        await self.logging_configurator_client._update_log_level()
        self.assertEqual(len(logging.getLogger('a').handlers), 1)
        self.assertEqual(len(logging.getLogger('b').handlers), 2)
        self.assertEqual(len(logging.getLogger('c').handlers), 2)

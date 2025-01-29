import logging
from typing import Optional

from fastapi import HTTPException

from frontik.dependencies import get_http_client
from frontik.loggers.logleveloverride.log_level_override_extension import LogLevelOverride, LogLevelOverrideExtension
from frontik.loggers.logleveloverride.logging_configurator_client import LOG_LEVEL_MAPPING
from frontik.util import generate_uniq_timestamp_request_id

logger = logging.getLogger('http_log_level_override_extension')


def parse_result_to_log_level_overrides_dto(data: Optional[dict]) -> list[LogLevelOverride]:
    result: list[LogLevelOverride] = []
    if data is None:
        return result

    for override in data['overrides']:
        log_override = LogLevelOverride(
            override['loggerName'],
            LOG_LEVEL_MAPPING.get(override['logLevel'], logging.INFO),
        )
        result.append(log_override)

    return result


class HttpLogLevelOverrideExtension(LogLevelOverrideExtension):
    def __init__(self, host: str, uri: str) -> None:
        self.host = host
        self.uri = uri

    async def load_log_level_overrides(self) -> list[LogLevelOverride]:
        headers = {'X-Request-Id': generate_uniq_timestamp_request_id()}
        result = await get_http_client().get_url(self.host, self.uri, headers=headers)
        if result.failed:
            logger.error('some problem with fetching log level overrides: %s', result.failed)
            raise HTTPException(result.status_code)

        log_level_overrides = parse_result_to_log_level_overrides_dto(result.data)
        return log_level_overrides

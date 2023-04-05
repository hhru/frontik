import logging
from typing import List

from http_client import HttpClientFactory
from tornado.httpclient import HTTPError

from frontik.loggers.logleveloverride.log_level_override_extension import LogLevelOverrideExtension, LogLevelOverride
from frontik.loggers.logleveloverride.logging_configurator_client import LOG_LEVEL_MAPPING
from frontik import request_context

logger = logging.getLogger('http_log_level_override_extension')


def parse_result_to_log_level_overrides_dto(data) -> List[LogLevelOverride]:
    result = []
    if data is None:
        return result

    for override in data['overrides']:
        log_override = LogLevelOverride(override['loggerName'],
                                        LOG_LEVEL_MAPPING.get(override['logLevel'], logging.INFO))
        result.append(log_override)

    return result


class HttpLogLevelOverrideExtension(LogLevelOverrideExtension):
    def __init__(self, host, uri, http_client_factory: HttpClientFactory):
        self.host = host
        self.uri = uri
        self.http_client_factory = http_client_factory

    async def load_log_level_overrides(self) -> List[LogLevelOverride]:
        headers = {
            'X-Request-Id': request_context.get_request_id()
        }
        result = await self.http_client_factory.get_http_client().get_url(self.host, self.uri, headers=headers)
        if result.failed:
            logger.error(f'some problem with fetching log level overrides: {result.failed}')
            raise HTTPError(result.response.code)

        log_level_overrides = parse_result_to_log_level_overrides_dto(result.data)
        return log_level_overrides

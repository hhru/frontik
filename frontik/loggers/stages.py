from __future__ import annotations

import logging
import time
from collections import namedtuple
from typing import TYPE_CHECKING

from frontik import request_context

if TYPE_CHECKING:
    from tornado.httputil import HTTPServerRequest

    from frontik.integrations.statsd import StatsDClient, StatsDClientStub

stages_logger = logging.getLogger('stages')


class StagesLogger:
    Stage = namedtuple('Stage', ('name', 'delta', 'start_delta'))

    def __init__(self, request: HTTPServerRequest, statsd_client: StatsDClient | StatsDClientStub) -> None:
        self._last_stage_time = self._start_time = request._start_time
        self._stages: list[StagesLogger.Stage] = []
        self._statsd_client = statsd_client

    def commit_stage(self, stage_name: str) -> None:
        stage_end_time = time.time()
        stage_start_time = self._last_stage_time
        self._last_stage_time = stage_end_time

        delta = (stage_end_time - stage_start_time) * 1000
        start_delta = (stage_start_time - self._start_time) * 1000
        stage = StagesLogger.Stage(stage_name, delta, start_delta)

        self._stages.append(stage)
        stages_logger.debug('stage "%s" completed in %.2fms', stage.name, stage.delta, extra={'_stage': stage})

    def flush_stages(self, status_code: int) -> None:
        """Writes available stages, total value and status code"""
        handler_name = request_context.get_handler_name()

        self._statsd_client.stack()

        for s in self._stages:
            self._statsd_client.time('handler.stage.time', int(s.delta), stage=s.name)

        self._statsd_client.flush()

        stages_str = ' '.join(f'{s.name}={s.delta:.2f}' for s in self._stages)
        total = sum(s.delta for s in self._stages)

        stages_logger.info(
            'timings for %(page)s : %(stages)s',
            {'page': handler_name, 'stages': f'{stages_str} total={total:.2f} code={status_code}'},
        )

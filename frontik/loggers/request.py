# coding=utf-8

import logging
import time
from collections import namedtuple

from frontik.request_context import RequestContext


class RequestLogger(logging.Logger):

    Stage = namedtuple('Stage', ('name', 'delta', 'start_delta'))

    def __init__(self, request):
        super(RequestLogger, self).__init__('frontik.handler')

        self._last_stage_time = self._start_time = request._start_time
        self.stages = []
        self.parent = logging.getLogger()

    def stage_tag(self, stage_name):
        stage_end_time = time.time()
        stage_start_time = self._last_stage_time
        self._last_stage_time = stage_end_time

        delta = (stage_end_time - stage_start_time) * 1000
        start_delta = (stage_start_time - self._start_time) * 1000
        stage = RequestLogger.Stage(stage_name, delta, start_delta)

        self.stages.append(stage)
        self.debug('stage "%s" completed in %.2fms', stage.name, stage.delta, extra={'_stage': stage})

    def get_current_total(self):
        return sum(s.delta for s in self.stages)

    def log_stages(self, status_code):
        """Writes available stages, total value and status code"""

        stages_str = ' '.join('{s.name}={s.delta:.2f}'.format(s=s) for s in self.stages)
        total = sum(s.delta for s in self.stages)

        self.info(
            'timings for %(page)s : %(stages)s',
            {
                'page': RequestContext.get('handler_name'),
                'stages': '{0} total={1:.2f} code={2}'.format(stages_str, total, status_code)
            },
        )

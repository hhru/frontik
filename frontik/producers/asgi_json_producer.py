import asyncio
import logging
import time
import weakref
from typing import Optional

import jinja2
from jinja2.utils import concat
from tornado.escape import to_unicode

from frontik import media_types
from frontik.auth import check_debug_auth_or_finish
from frontik.debug import DebugMode
from frontik.options import options
from frontik.producers import ProducerFactory
from frontik.util import get_abs_path, get_cookie_or_url_param_value
from fastapi import Request, Depends
from frontik.json_builder import JsonBuilder
from typing import Annotated
from typing import Any


log = logging.getLogger('handler')


class JsonProducer:
    def __init__(
        self,
        debug_mode: DebugMode,
        jinja_environment: Optional[jinja2.Environment] = None,
    ) -> None:
        self.json = JsonBuilder()
        self.template_filename: Optional[str] = None
        self.debug_mode = debug_mode
        self.jinja_environment = jinja_environment

    def set_template(self, filename: str) -> None:
        self.template_filename = filename

    async def render(self) -> tuple[str, str]:  # response_body, content_type
        if self.debug_mode.notpl and self.debug_mode.enabled:
            log.debug('ignoring templating because notpl parameter is passed')
            return await self._finish_with_json()

        if self.template_filename:
            return await self._finish_with_template()

        return await self._finish_with_json()

    async def _finish_with_json(self) -> tuple[str, str]:
        log.debug('finishing without templating')
        return self.json.to_string(), media_types.APPLICATION_JSON

    async def _finish_with_template(self) -> tuple[str, str]:
        if not self.jinja_environment:
            raise Exception('Cannot apply template, no Jinja2 environment configured')

        try:
            render_result, render_time = await self._render_template_stream(options.jinja_streaming_render_timeout_ms)
            log.info('applied template %s in %.2fms', self.template_filename, render_time * 1000)
            return render_result, media_types.TEXT_HTML

        except Exception as e:
            log.error('failed applying template %s', self.template_filename)

            if isinstance(e, jinja2.TemplateSyntaxError):
                log.error(
                    '%s in file "%s", line %d\n\t%s',
                    e.__class__.__name__,
                    to_unicode(e.filename),
                    e.lineno,
                    to_unicode(e.message),
                )
            elif isinstance(e, jinja2.TemplateError):
                log.error('%s error\n\t%s', e.__class__.__name__, to_unicode(e.message))

            raise e

    async def _render_template_stream(self, batch_render_timeout_ms: int) -> tuple[str, float]:
        template_render_time = 0
        template = self.jinja_environment.get_template(self.template_filename)

        template_stream = template.generate(self.json.to_dict())
        template_parts = []

        part_index = 1
        while True:
            part_render_start_time = time.time()
            if batch_render_timeout_ms is not None:
                part_render_timeout_time = part_render_start_time + batch_render_timeout_ms / 1000.0
            else:
                part_render_timeout_time = None

            whole_template_render_finished = False
            statements_processed = 0

            while True:
                next_statement_render_result = next(template_stream, None)

                if next_statement_render_result is None:
                    whole_template_render_finished = True
                    break

                statements_processed += 1
                template_parts.append(next_statement_render_result)

                if part_render_timeout_time is not None and time.time() > part_render_timeout_time:
                    break

            taken_time_ms = (time.time() - part_render_start_time) * 1000
            template_render_time += taken_time_ms
            log.info(
                'render template part %s with %s statements in %.2fms',
                part_index,
                statements_processed,
                taken_time_ms,
            )

            part_index += 1

            if whole_template_render_finished:
                return concat(template_parts), template_render_time

            await asyncio.sleep(0)

    def __repr__(self):
        return f'{__package__}.{self.__class__.__name__}'


async def get_json_producer(request: Request) -> JsonProducer:
    return request.state.json_producer


JsonProducerT = Annotated[JsonProducer, Depends(get_json_producer)]

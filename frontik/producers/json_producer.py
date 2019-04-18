import asyncio
import time
import weakref

import jinja2
from jinja2.utils import concat
from tornado.escape import to_unicode
from tornado.options import options

from frontik import json_builder, media_types
from frontik.util import get_abs_path, get_cookie_or_url_param_value
from frontik.producers import ProducerFactory


class JsonProducerFactory(ProducerFactory):
    def __init__(self, application):
        if hasattr(application, 'get_jinja_environment'):
            self.environment = application.get_jinja_environment()
        elif options.jinja_template_root is not None:
            self.environment = jinja2.Environment(
                auto_reload=options.debug,
                cache_size=options.jinja_template_cache_limit,
                loader=jinja2.FileSystemLoader(get_abs_path(application.app_root, options.jinja_template_root)),
            )
        else:
            self.environment = None

    def get_producer(self, handler):
        return JsonProducer(
            handler,
            environment=self.environment,
            json_encoder=getattr(handler, 'json_encoder', None),
            jinja_context_provider=getattr(handler, 'jinja_context_provider', None),
        )


class JsonProducer:
    def __init__(self, handler, environment=None, json_encoder=None, jinja_context_provider=None):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)

        self.json = json_builder.JsonBuilder(json_encoder=json_encoder)
        self.template_filename = None
        self.environment = environment
        self.jinja_context_provider = jinja_context_provider

    def __call__(self):
        if get_cookie_or_url_param_value(self.handler, 'notpl') is not None:
            self.handler.require_debug_access()
            self.log.debug('ignoring templating because notpl parameter is passed')
            return self._finish_with_json()

        if self.template_filename:
            return self._finish_with_template()

        return self._finish_with_json()

    def set_template(self, filename):
        self.template_filename = filename

    def get_jinja_context(self):
        if callable(self.jinja_context_provider):
            return self.jinja_context_provider(self.handler)
        else:
            return self.json.to_dict()

    async def _render_template_stream_on_ioloop(self, batch_render_timeout_ms):
        template_render_start_time = time.time()
        template = self.environment.get_template(self.template_filename)

        template_stream = template.generate(self.get_jinja_context())
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
            self.log.info(
                'render template part %s with %s statements in %.2fms', part_index, statements_processed, taken_time_ms
            )

            part_index += 1

            if whole_template_render_finished:
                return template_render_start_time, concat(template_parts)

            await asyncio.sleep(0)

    async def _finish_with_template(self):
        if not self.environment:
            raise Exception('Cannot apply template, no Jinja2 environment configured')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.TEXT_HTML)

        try:
            render_result = await self._render_template_stream_on_ioloop(options.jinja_streaming_render_timeout_ms)
            if self.handler.is_finished():
                return None

            start_time, result = render_result

            self.handler.stages_logger.commit_stage('tpl')
            self.log.info('applied template %s in %.2fms', self.template_filename, (time.time() - start_time) * 1000)

            return result

        except Exception as e:
            self.log.error('failed applying template %s', self.template_filename)

            if isinstance(e, jinja2.TemplateSyntaxError):
                self.log.error(
                    '%s in file "%s", line %d\n\t%s',
                    e.__class__.__name__, to_unicode(e.filename), e.lineno, to_unicode(e.message)
                )
            elif isinstance(e, jinja2.TemplateError):
                self.log.error('%s error\n\t%s', e.__class__.__name__, to_unicode(e.message))

            raise e

    async def _finish_with_json(self):
        self.log.debug('finishing without templating')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.APPLICATION_JSON)

        return self.json.to_string()

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)

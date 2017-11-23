# coding=utf-8

import time
import weakref
from functools import partial

import jinja2
import sys
import tornado.ioloop
from jinja2.utils import concat
from tornado.concurrent import TracebackFuture
from tornado.escape import to_unicode, utf8
from tornado.options import options

import frontik.jobs
import frontik.json_builder
from frontik.util import get_cookie_or_url_param_value, raise_future_exception
from frontik.producers import ProducerFactory


class JsonProducerFactory(ProducerFactory):
    def __init__(self, application):
        if hasattr(application, 'get_jinja_environment'):
            self.environment = application.get_jinja_environment()
        elif getattr(application.config, 'template_root', None) is not None:
            self.environment = jinja2.Environment(
                auto_reload=options.debug,
                cache_size=getattr(application.config, 'template_cache_limit', 50),
                loader=jinja2.FileSystemLoader(application.config.template_root),
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


class JsonProducer(object):
    def __init__(self, handler, environment=None, json_encoder=None, jinja_context_provider=None):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)
        self.executor = frontik.jobs.get_executor(options.json_executor)
        self.ioloop = tornado.ioloop.IOLoop.current()

        self.json = frontik.json_builder.JsonBuilder(json_encoder=json_encoder)
        self.template_filename = None
        self.environment = environment
        self.jinja_context_provider = jinja_context_provider

    def __call__(self, callback):
        if get_cookie_or_url_param_value(self.handler, 'notpl') is not None:
            self.handler.require_debug_access()
            self.log.debug('ignoring templating because notpl parameter is passed')
            return self._finish_with_json(callback)

        if self.template_filename:
            self._finish_with_template(callback)
        else:
            self._finish_with_json(callback)

    def set_template(self, filename):
        self.template_filename = filename

    def get_jinja_context(self):
        if callable(self.jinja_context_provider):
            return self.jinja_context_provider(self.handler)
        else:
            return self.json.to_dict()

    def _render_template_stream_on_ioloop(self, batch_render_timeout_ms):
        render_future = TracebackFuture()
        template_render_start_time = time.time()
        template = self.environment.get_template(self.template_filename)

        template_stream = template.generate(self.get_jinja_context())
        template_parts = []

        def _render_template_part(part_index=1):
            whole_template_render_finished = False
            part_render_start_time = time.time()
            part_render_timeout_time = part_render_start_time + batch_render_timeout_ms / 1000.0

            statements_processed = 0

            while True:
                try:
                    next_statement_render_result = next(template_stream, None)
                except Exception:
                    render_future.set_exc_info(sys.exc_info())
                    return

                if next_statement_render_result is None:
                    whole_template_render_finished = True
                    break
                statements_processed += 1
                template_parts.append(next_statement_render_result)

                if time.time() > part_render_timeout_time:
                    break

            taken_time_ms = (time.time() - part_render_start_time) * 1000
            self.log.info(
                'render template part %i with %i statements in %.2fms',
                part_index, statements_processed, taken_time_ms
            )

            if whole_template_render_finished:
                render_future.set_result((template_render_start_time, concat(template_parts)))
            else:
                self.ioloop.add_callback(partial(_render_template_part, part_index + 1))

        _render_template_part()
        return render_future

    def _render_template_on_executor(self):
        def render_job():
            start_time = time.time()
            template = self.environment.get_template(self.template_filename)
            result = template.render(**self.get_jinja_context())
            return start_time, result

        return self.executor.submit(render_job)

    def _get_jinja_streaming_render_timeout(self):
        render_timeout_provider = getattr(self.handler, 'get_jinja_streaming_render_timeout', None)
        if callable(render_timeout_provider):
            return render_timeout_provider()

    def _finish_with_template(self, callback):
        if not self.environment:
            raise Exception('Cannot apply template, no Jinja2 environment configured')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'text/html; charset=utf-8')

        jinja_streaming_render_timeout = self._get_jinja_streaming_render_timeout()

        if jinja_streaming_render_timeout:
            render_future = self._render_template_stream_on_ioloop(jinja_streaming_render_timeout)
        else:
            render_future = self._render_template_on_executor()

        def job_callback(future):
            if future.exception() is not None:
                self.log.error('failed applying template %s', self.template_filename)

                exception = future.exception()
                if isinstance(exception, jinja2.TemplateSyntaxError):
                    self.log.error(
                        u'%s in file "%s", line %d\n\t%s',
                        exception.__class__.__name__, to_unicode(exception.filename),
                        exception.lineno, to_unicode(exception.message)
                    )
                elif isinstance(exception, jinja2.TemplateError):
                    self.log.error(u'%s error\n\t%s', exception.__class__.__name__, to_unicode(exception.message))

                raise_future_exception(future)
                return

            start_time, result = future.result()

            self.log.stage_tag('tpl')
            self.log.info('applied template %s in %.2fms', self.template_filename, (time.time() - start_time) * 1000)

            callback(utf8(result))

        self.ioloop.add_future(render_future, self.handler.check_finished(job_callback))
        return render_future

    def _finish_with_json(self, callback):
        self.log.debug('finishing without templating')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'application/json; charset=utf-8')
        callback(utf8(self.json.to_string()))

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)

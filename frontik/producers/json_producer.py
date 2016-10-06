# coding=utf-8

import time
import weakref

import jinja2
import tornado.ioloop
from tornado.concurrent import TracebackFuture
from tornado.escape import to_unicode, utf8
from tornado.options import options
from tornado.util import raise_exc_info

import frontik.jobs
import frontik.json_builder
import frontik.util
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
        self.ioloop = tornado.ioloop.IOLoop.instance()

        self.json = frontik.json_builder.JsonBuilder(json_encoder=json_encoder, logger=self.log)
        self.template_filename = None
        self.environment = getattr(environment, 'environment', environment)  # Temporary for transition period
        self.jinja_context_provider = jinja_context_provider

    def __call__(self, callback):
        if frontik.util.get_cookie_or_url_param_value(self.handler, 'notpl') is not None:
            self.handler.require_debug_access()
            self.log.debug('ignoring templating because notpl parameter is passed')
            return self._finish_with_json(callback)

        if self.template_filename:
            self._finish_with_template(callback)
        else:
            self._finish_with_json(callback)

    def set_template(self, filename):
        self.template_filename = filename

    def _finish_with_template(self, callback):
        if not self.environment:
            raise Exception('Cannot apply template, no Jinja2 environment configured')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'text/html; charset=utf-8')

        def job():
            start_time = time.time()
            template = self.environment.get_template(self.template_filename)

            if callable(self.jinja_context_provider):
                jinja_context = self.jinja_context_provider(self.handler)
            else:
                jinja_context = self.json.to_dict()

            result = template.render(**jinja_context)
            return start_time, result

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

                if isinstance(future, TracebackFuture):
                    raise_exc_info(future.exc_info())
                else:
                    raise exception

            start_time, result = future.result()

            self.log.stage_tag('tpl')
            self.log.info('applied template %s in %.2fms', self.template_filename, (time.time() - start_time) * 1000)

            callback(utf8(result))

        future = self.executor.submit(job)
        self.ioloop.add_future(future, self.handler.check_finished(job_callback))
        return future

    def _finish_with_json(self, callback):
        self.log.debug('finishing without templating')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'application/json; charset=utf-8')
        callback(utf8(self.json.to_string()))

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)

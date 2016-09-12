# coding=utf-8

import time
import weakref

import jinja2
import tornado.ioloop
from tornado.options import options

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
            render_kwargs_provider=getattr(handler, 'jinja_render_kwargs', None),
        )


class JsonProducer(object):
    def __init__(self, handler, environment=None, json_encoder=None, render_kwargs_provider=None):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)
        self.executor = frontik.jobs.get_executor(options.json_executor)
        self.ioloop = tornado.ioloop.IOLoop.instance()

        self.json = frontik.json_builder.JsonBuilder(json_encoder=json_encoder, logger=self.log)
        self.template_filename = None
        self.environment = environment
        self.render_kwargs_provider = render_kwargs_provider

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
            raise Exception('Cannot apply template, option "template_root" is not set in application config')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'text/html; charset=utf-8')

        def job():
            start_time = time.time()
            template = self.environment.get_template(self.template_filename)

            if callable(self.render_kwargs_provider):
                render_kwargs = self.render_kwargs_provider(self.handler)
            else:
                render_kwargs = self.json.to_dict()

            result = template.render(**render_kwargs)
            return start_time, result

        def job_callback(future):
            if future.exception() is not None:
                self.log.error('failed applying template %s', self.template_filename)

                exception = future.exception()
                if isinstance(exception, jinja2.TemplateSyntaxError):
                    self.log.error(
                        'jinja %s in file "%s", line %d\n\t$s',
                        exception.__class__.__name__, exception.filename, exception.lineno, exception.message
                    )
                elif isinstance(exception, jinja2.TemplateError):
                    self.log.error('jinja %s error\n\t%s', exception.__class__.__name__, exception.message)

                raise exception

            start_time, result = future.result()

            self.log.stage_tag('tpl')
            self.log.info('applied template %s in %.2fms', self.template_filename, (time.time() - start_time) * 1000)

            callback(result)

        future = self.executor.submit(job)
        self.ioloop.add_future(future, self.handler.check_finished(job_callback))
        return future

    def _finish_with_json(self, callback):
        self.log.debug('finishing without templating')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'application/json; charset=utf-8')
        callback(self.json.to_string())

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)

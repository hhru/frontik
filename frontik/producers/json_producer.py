# coding=utf-8

import time
import weakref

import jinja2
import tornado.options

import frontik.jobs
import frontik.json_builder
import frontik.util


class ApplicationJsonGlobals(object):
    def __init__(self, config):
        cache_size = getattr(config, 'template_cache_limit', 50)
        template_root = getattr(config, 'template_root', None)

        if template_root:
            self.environment = jinja2.Environment(
                cache_size=cache_size,
                auto_reload=tornado.options.options.autoreload,
                loader=jinja2.FileSystemLoader(template_root)
            )
        else:
            self.environment = None


class JsonProducer(object):
    def __init__(self, handler, json_globals, json_encoder):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)
        self.executor = frontik.jobs.get_executor(tornado.options.options.json_executor)

        self.json = frontik.json_builder.JsonBuilder(json_encoder=json_encoder)
        self.template_filename = None
        self.environment = json_globals.environment

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
            result = template.render(self.json.to_dict())
            return start_time, result

        def success_cb(result):
            start_time, result = result

            self.log.stage_tag('tpl')
            self.log.debug('applied template {0} in {1:.2f}ms'.format(
                self.template_filename, (time.time() - start_time) * 1000))

            callback(result)

        def exception_cb(exception):
            self.log.error('failed applying template %s', self.template_filename)
            raise exception

        self.executor.add_job(job, self.handler.async_callback(success_cb), self.handler.async_callback(exception_cb))

    def _finish_with_json(self, callback):
        self.log.debug('finishing without templating')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'application/json; charset=utf-8')
        callback(self.json.to_string())

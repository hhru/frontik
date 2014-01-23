# coding=utf-8

import time
import weakref

import jinja2
import tornado.options

import frontik.jobs
import frontik.json_holder


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
    def __init__(self, handler, json_globals):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)

        if tornado.options.options.json_executor == 'threaded':
            self.executor = frontik.jobs.get_threadpool_executor()
        elif tornado.options.options.json_executor == 'ioloop':
            self.executor = frontik.jobs.IOLoopExecutor
        else:
            raise ValueError('Cannot initialize JsonProducer with executor_type {0!r}'.format(
                tornado.options.options.executor_type))

        self.json = frontik.json_holder.JsonHolder()
        self.template_filename = None
        self.environment = json_globals.environment

    def __call__(self, handler, callback):
        if self.template_filename:
            self._finish_with_template(handler, callback)
        else:
            self._finish_with_json(handler, callback)

    def set_template(self, filename):
        self.template_filename = filename

    def _finish_with_template(self, handler, callback):
        if not self.environment:
            raise Exception('Cannot apply template, option "template_root" is not set in application config')

        if not self.handler._headers.get('Content-Type', None):
            self.handler.set_header('Content-Type', 'text/html')

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

    def _finish_with_json(self, handler, callback):
        self.log.debug('finishing without templating')
        self.handler.set_header('Content-Type', 'application/json')
        callback(self.json.to_string())

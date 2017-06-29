# coding=utf-8

import importlib
import logging
import os
import re

from frontik.compat import iteritems
from frontik.handler import ErrorHandler
from frontik.util import reverse_regex_named_groups

routing_logger = logging.getLogger('frontik.routing')

MAX_MODULE_NAME_LENGTH = os.pathconf('/', 'PC_PATH_MAX') - 1


class FileMappingRouter(object):
    def __init__(self, module):
        self.name = module.__name__

    def __call__(self, application, request, **kwargs):
        url_parts = request.path.strip('/').split('/')

        if any('.' in part for part in url_parts):
            routing_logger.info('url contains "." character, using 404 page')
            return self.handle_404(application, request, **kwargs)

        page_name = '.'.join(filter(None, url_parts))
        page_module_name = '.'.join(filter(None, (self.name, page_name)))
        routing_logger.debug('page module: %s', page_module_name)

        if len(page_module_name) > MAX_MODULE_NAME_LENGTH:
            routing_logger.info('page module name exceeds PATH_MAX (%s), using 404 page', MAX_MODULE_NAME_LENGTH)
            return self.handle_404(application, request, **kwargs)

        try:
            page_module = importlib.import_module(page_module_name)
            routing_logger.debug('using %s from %s', page_module_name, page_module.__file__)
        except ImportError:
            routing_logger.warning('%s module not found', (self.name, page_module_name))
            return self.handle_404(application, request, **kwargs)
        except:
            routing_logger.exception('error while importing %s module', page_module_name)
            return ErrorHandler(application, request, status_code=500, **kwargs)

        if not hasattr(page_module, 'Page'):
            routing_logger.error('%s.Page class not found', page_module_name)
            return self.handle_404(application, request, **kwargs)

        return page_module.Page(application, request, **kwargs)

    def handle_404(self, application, request, **kwargs):
        handler_class, handler_kwargs = application.application_404_handler(request)
        return handler_class(application, request, **dict(kwargs, **handler_kwargs))


class FrontikRouter(object):
    def __init__(self, application):
        self.application = application
        self.handlers = []
        self.handler_names = {}

        for handler_spec in application.application_urls():
            if len(handler_spec) > 2:
                pattern, handler, handler_name = handler_spec
            else:
                handler_name = None
                pattern, handler = handler_spec

            self.handlers.append((re.compile(pattern), handler))

            if handler_name is not None:
                self.handler_names[handler_name] = pattern

    def __call__(self, application, request, **kwargs):
        routing_logger.info('requested url: %s', request.uri)

        for pattern, handler in self.handlers:
            match = pattern.match(request.uri)
            if match:
                routing_logger.debug('using %r', handler)
                extend_request_arguments(request, match)
                try:
                    return handler(application, request, **kwargs)
                except Exception as e:
                    routing_logger.exception('error handling request: %s in %r', e, handler)
                    return ErrorHandler(application, request, status_code=500, **kwargs)

        routing_logger.error('match for request url "%s" not found', request.uri)
        return self.handle_404(application, request, **kwargs)

    def reverse_url(self, name, *args, **kwargs):
        if name not in self.handler_names:
            raise KeyError('%s not found in named urls' % name)

        return reverse_regex_named_groups(self.handler_names[name], *args, **kwargs)

    def handle_404(self, application, request, **kwargs):
        handler_class, handler_kwargs = application.application_404_handler(request)
        return handler_class(application, request, **dict(kwargs, **handler_kwargs))


def extend_request_arguments(request, match):
    arguments = match.groupdict()
    for name, value in iteritems(arguments):
        if value:
            request.arguments.setdefault(name, []).append(value)

# coding=utf-8

import importlib
import logging
import os
import re

from frontik.compat import iteritems
from frontik.handler import ErrorHandler
from frontik.loggers.request import RequestLogger
from frontik.util import reverse_regex_named_groups

routing_logger = logging.getLogger('frontik.routing')

MAX_MODULE_NAME_LENGTH = os.pathconf('/', 'PC_PATH_MAX') - 1


class FileMappingRouter(object):
    def __init__(self, module):
        self.name = module.__name__

    def __call__(self, application, request, logger, **kwargs):
        url_parts = request.path.strip('/').split('/')

        if any('.' in part for part in url_parts):
            logger.info('url contains "." character, using 404 page')
            return self.handle_404(application, request, logger, **kwargs)

        page_name = '.'.join(filter(None, url_parts))
        page_module_name = '.'.join(filter(None, (self.name, page_name)))
        logger.debug('page module: %s', page_module_name)

        if len(page_module_name) > MAX_MODULE_NAME_LENGTH:
            logger.info('page module name exceeds PATH_MAX (%s), using 404 page', MAX_MODULE_NAME_LENGTH)
            return self.handle_404(application, request, logger, **kwargs)

        try:
            page_module = importlib.import_module(page_module_name)
            logger.debug('using %s from %s', page_module_name, page_module.__file__)
        except ImportError:
            logger.warning('%s module not found', (self.name, page_module_name))
            return self.handle_404(application, request, logger, **kwargs)
        except:
            logger.exception('error while importing %s module', page_module_name)
            return ErrorHandler(application, request, logger=logger, status_code=500, **kwargs)

        if not hasattr(page_module, 'Page'):
            logger.error('%s.Page class not found', page_module_name)
            return self.handle_404(application, request, logger, **kwargs)

        return page_module.Page(application, request, logger=logger, **kwargs)

    def handle_404(self, application, request, logger, **kwargs):
        handler_class, handler_kwargs = application.application_404_handler(request)
        return handler_class(application, request, logger=logger, **dict(kwargs, **handler_kwargs))


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
        request_logger = RequestLogger(request)

        request_logger.info('requested url: %s', request.uri)

        for pattern, handler in self.handlers:
            match = pattern.match(request.uri)
            if match:
                request_logger.debug('using %r', handler)
                extend_request_arguments(request, match)
                try:
                    return handler(application, request, logger=request_logger, **kwargs)
                except Exception as e:
                    request_logger.exception('error handling request: %s in %r', e, handler)
                    return ErrorHandler(application, request, logger=request_logger, status_code=500, **kwargs)

        request_logger.error('match for request url "%s" not found', request.uri)
        return self.handle_404(application, request, request_logger, **kwargs)

    def reverse_url(self, name, *args, **kwargs):
        if name not in self.handler_names:
            raise KeyError('%s not found in named urls' % name)

        return reverse_regex_named_groups(self.handler_names[name], *args, **kwargs)

    def handle_404(self, application, request, logger, **kwargs):
        handler_class, handler_kwargs = application.application_404_handler(request)
        return handler_class(application, request, logger=logger, **dict(kwargs, **handler_kwargs))


def extend_request_arguments(request, match):
    arguments = match.groupdict()
    for name, value in iteritems(arguments):
        if value:
            request.arguments.setdefault(name, []).append(value)

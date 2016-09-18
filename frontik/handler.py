# coding=utf-8

import base64
from functools import partial, wraps
import time

import tornado.curl_httpclient
import tornado.httputil
import tornado.options
import tornado.web
from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from tornado.util import raise_exc_info

from frontik.async import AsyncGroup, dependency, DependencyChain
import frontik.auth
from frontik.compat import iteritems
import frontik.handler_active_limit
from frontik.handler_debug import PageHandlerDebug
from frontik.http_client import HttpClient
from frontik.http_codes import process_status_code
import frontik.producers.json_producer
import frontik.producers.xml_producer
import frontik.util


class HTTPError(tornado.web.HTTPError):
    """Extends tornado.web.HTTPError with several keyword-only arguments and allows using some extended HTTP codes.

    :arg dict headers: Custom HTTP headers to pass along with the error response.
    :arg string text: Plain text override for error response.
    :arg etree xml: XML node to be added to `self.doc`. If present, error page will be
        produced with `application/xml` content type.
    :arg dict json: JSON dict to be used as error response. If present, error page
        will be produced with `application/json` content type.
    """
    def __init__(self, status_code, log_message=None, *args, **kwargs):
        headers = kwargs.pop('headers', {})
        for data in ('text', 'xml', 'json'):
            setattr(self, data, kwargs.pop(data, None))

        status_code, kwargs['reason'] = process_status_code(status_code, kwargs.get('reason'))
        super(HTTPError, self).__init__(status_code, log_message, *args, **kwargs)
        self.headers = headers


class BaseHandler(tornado.web.RequestHandler):

    preprocessors = ()

    # to restore tornado.web.RequestHandler compatibility
    def __init__(self, application, request, logger, request_id=None, **kwargs):
        self._prepared = False

        if request_id is None:
            raise Exception('no request_id for {} provided'.format(self.__class__))

        self.name = self.__class__.__name__
        self.request_id = request_id
        self.config = application.config

        self.log = logger
        self._exception_hooks = []

        for initializer in application.loggers_initializers:
            initializer(self)

        super(BaseHandler, self).__init__(application, request, logger=self.log, **kwargs)

        self.log.register_page_handler(self)
        self._debug_access = None

        self._template_postprocessors = []
        self._early_postprocessors = []
        self._late_postprocessors = []
        self._dependency_scheduler = DependencyChain(bound_args=(self,))

        self._http_client = HttpClient(self, self.application.curl_http_client, self.modify_http_client_request)

        self.text = None

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def initialize(self, logger=None, **kwargs):
        # Hides logger keyword argument from incompatible tornado versions
        super(BaseHandler, self).initialize(**kwargs)

    def prepare(self):
        self.active_limit = frontik.handler_active_limit.PageHandlerActiveLimit(self)
        self.debug = PageHandlerDebug(self)

        self.json_producer = frontik.producers.json_producer.JsonProducer(
            self, self.application.json, getattr(self, 'json_encoder', None))
        self.json = self.json_producer.json

        self.xml_producer = frontik.producers.xml_producer.XmlProducer(self, self.application.xml)
        self.xml = self.xml_producer  # deprecated synonym
        self.doc = self.xml_producer.doc
        self.finish_group = AsyncGroup(self.check_finished(self._finish_page_cb), name='finish', logger=self.log)
        self._prepared = True

    def require_debug_access(self, login=None, passwd=None):
        if self._debug_access is None:
            if tornado.options.options.debug:
                debug_access = True
            else:
                check_login = login if login is not None else tornado.options.options.debug_login
                check_passwd = passwd if passwd is not None else tornado.options.options.debug_password
                error = frontik.auth.check_debug_auth(self, check_login, check_passwd)
                debug_access = (error is None)
                if not debug_access:
                    code, headers = error
                    raise HTTPError(code, headers=headers)

            self._debug_access = debug_access

    def set_default_headers(self):
        self._headers = tornado.httputil.HTTPHeaders({
            'Server': 'Frontik/{0}'.format(frontik.version),
            'X-Request-Id': self.request_id,
        })

    def decode_argument(self, value, name=None):
        try:
            return super(BaseHandler, self).decode_argument(value, name)
        except (UnicodeError, tornado.web.HTTPError):
            self.log.warning('cannot decode utf-8 query parameter, trying other charsets')

        try:
            return frontik.util.decode_string_from_charset(value)
        except UnicodeError:
            self.log.exception('cannot decode argument, ignoring invalid chars')
            return value.decode('utf-8', 'ignore')

    def set_status(self, status_code, reason=None):
        status_code, reason = process_status_code(status_code, reason)
        super(BaseHandler, self).set_status(status_code, reason=reason)

    @staticmethod
    def add_callback(callback):
        IOLoop.instance().add_callback(callback)

    @staticmethod
    def add_timeout(deadline, callback):
        IOLoop.instance().add_timeout(deadline, callback)

    @staticmethod
    def add_future(future, callback):
        IOLoop.instance().add_future(future, callback)

    # Requests handling

    @tornado.web.asynchronous
    def get(self, *args, **kwargs):
        self.log.stage_tag('prepare')

        self.add_future(
            self._dependency_scheduler.resolve(
                DependencyChain.get_dependencies(self.add_preprocessor(*self.preprocessors)(self.get_page.__func__))
            ),
            self._create_handler_method_wrapper(self.get_page)
        )

    @tornado.web.asynchronous
    def post(self, *args, **kwargs):
        self.log.stage_tag('prepare')

        self.add_future(
            self._dependency_scheduler.resolve(
                DependencyChain.get_dependencies(self.add_preprocessor(*self.preprocessors)(self.post_page.__func__))
            ),
            self._create_handler_method_wrapper(self.post_page)
        )

    @tornado.web.asynchronous
    def head(self, *args, **kwargs):
        self.log.stage_tag('prepare')

        self.add_future(
            self._dependency_scheduler.resolve(
                DependencyChain.get_dependencies(self.add_preprocessor(*self.preprocessors)(self.get_page.__func__))
            ),
            self._create_handler_method_wrapper(self.get_page)
        )

    @tornado.web.asynchronous
    def delete(self, *args, **kwargs):
        self.log.stage_tag('prepare')

        self.add_future(
            self._dependency_scheduler.resolve(
                DependencyChain.get_dependencies(self.add_preprocessor(*self.preprocessors)(self.delete_page.__func__))
            ),
            self._create_handler_method_wrapper(self.delete_page)
        )

    @tornado.web.asynchronous
    def put(self, *args, **kwargs):
        self.log.stage_tag('prepare')

        self.add_future(
            self._dependency_scheduler.resolve(
                DependencyChain.get_dependencies(self.add_preprocessor(*self.preprocessors)(self.put_page.__func__))
            ),
            self._create_handler_method_wrapper(self.put_page)
        )

    def _create_handler_method_wrapper(self, handler_method):
        notification = self.finish_group.add_notification()

        def _handle_future(future):
            if future.exception():
                raise_exc_info(future.exc_info())

            return_value = handler_method()

            if hasattr(self, 'handle_return_value'):
                method_name = handler_method.__name__
                self.handle_return_value(method_name, return_value)

            notification()

        return _handle_future

    def options(self, *args, **kwargs):
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def get_page(self):
        """ This method can be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def post_page(self):
        """ This method can be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def put_page(self):
        """ This method can be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def delete_page(self):
        """ This method can be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def __get_allowed_methods(self):
        return [name for name in ('get', 'post', 'put', 'delete') if '{0}_page'.format(name) in vars(self.__class__)]

    # HTTP client methods

    def modify_http_client_request(self, request):
        return request

    # Finish page

    def check_finished(self, callback, *args, **kwargs):
        original_callback = callback
        if args or kwargs:
            callback = partial(callback, *args, **kwargs)

        def wrapper(*args, **kwargs):
            if self._finished:
                self.log.warn('page was already finished, {0} ignored'.format(original_callback))
            else:
                callback(*args, **kwargs)

        return wrapper

    def _finish_page(self):
        self.finish_group.try_finish()

    def finish_with_postprocessors(self):
        self.finish_group.finish()

    def _finish_page_cb(self):
        if not self._finished:
            def _callback():
                self.log.stage_tag('page')

                if self.text is not None:
                    producer = self._generic_producer
                elif not self.json.is_empty():
                    producer = self.json_producer
                else:
                    producer = self.xml_producer

                self.log.debug('using %s producer', producer)
                producer(partial(self._call_postprocessors, self._template_postprocessors, self.finish))

            self._call_postprocessors(self._early_postprocessors, _callback)
        else:
            self.log.warning('trying to finish already finished page, probably bug in a workflow, ignoring')

    def on_connection_close(self):
        self.finish_group.abort()
        self.log.stage_tag('page')
        self.log.log_stages(408)
        self.cleanup()

    def register_exception_hook(self, exception_hook):
        """
        Adds a function to the list of hooks, which are executed when `log_exception` is called.
        `exception_hook` must have the same signature as `log_exception`
        """
        self._exception_hooks.append(exception_hook)

    def log_exception(self, typ, value, tb):
        super(BaseHandler, self).log_exception(typ, value, tb)

        for exception_hook in self._exception_hooks:
            exception_hook(typ, value, tb)

    def send_error(self, status_code=500, **kwargs):
        self.log.stage_tag('page')

        if self._headers_written:
            super(BaseHandler, self).send_error(status_code, **kwargs)

        self.clear()

        reason = None
        if 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
            if isinstance(exception, HTTPError) and exception.reason:
                reason = exception.reason

        self.set_status(status_code, reason=reason)

        try:
            self.write_error(status_code, **kwargs)
        except Exception:
            self.log.exception('Uncaught exception in write_error')
            if not self._finished:
                self.finish()

    def write_error(self, status_code=500, **kwargs):
        # write_error in Frontik must be asynchronous when handling custom errors (due to XSLT)
        # e.g. raise HTTPError(503) is syncronous and generates a standard Tornado error page,
        # whereas raise HTTPError(503, xml=...) will call finish_with_postprocessors()

        # the solution is to move self.finish() from send_error to write_error
        # so any write_error override must call either finish() or finish_with_postprocessors() in the end

        # in Tornado 3 it may be better to rewrite this mechanism with futures

        if 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
        else:
            exception = None

        headers = getattr(exception, 'headers', None)
        override_content = any(getattr(exception, x, None) is not None for x in ('text', 'xml', 'json'))

        finish_with_exception = exception is not None and (
            199 < status_code < 400 or  # raise HTTPError(200) to finish page immediately
            override_content
        )

        if headers:
            for (name, value) in iteritems(headers):
                self.set_header(name, value)

        if finish_with_exception:
            self.json.clear()

            if getattr(exception, 'text', None) is not None:
                self.doc.clear()
                self.text = exception.text
            elif getattr(exception, 'json', None) is not None:
                self.text = None
                self.doc.clear()
                self.json.put(exception.json)
            elif getattr(exception, 'xml', None) is not None:
                self.text = None
                # cannot clear self.doc due to backwards compatibility, a bug actually
                self.doc.put(exception.xml)

            self.finish_with_postprocessors()
            return

        self.set_header('Content-Type', 'text/html; charset=UTF-8')
        return super(BaseHandler, self).write_error(status_code, **kwargs)

    def cleanup(self):
        if hasattr(self, 'active_limit'):
            self.active_limit.release()

    def finish(self, chunk=None):
        def _finish_with_async_hook():
            self.log.stage_tag('postprocess')
            super(BaseHandler, self).finish(chunk)
            self.cleanup()

        try:
            self._call_postprocessors(self._late_postprocessors, _finish_with_async_hook)
        except:
            self.log.exception('error during late postprocessing stage, finishing with an exception')
            self._status_code = 500
            _finish_with_async_hook()

    def flush(self, include_footers=False, **kwargs):
        self.log.stage_tag('finish')
        self.log.info('finished handler %r', self)

        if self._prepared and self.debug.debug_mode.enabled:
            try:
                self._response_size = sum(map(len, self._write_buffer))
                original_headers = {'Content-Length': str(self._response_size)}
                response_headers = dict(self._headers, **original_headers)

                original_response = {
                    'buffer': base64.b64encode(b''.join(self._write_buffer)),
                    'headers': response_headers,
                    'code': self._status_code
                }

                res = self.debug.get_debug_page(
                    self._status_code, response_headers, original_response, self.log.get_current_total()
                )

                if self.debug.debug_mode.inherited:
                    self.set_header(PageHandlerDebug.DEBUG_HEADER_NAME, True)

                self.set_header('Content-disposition', '')
                self.set_header('Content-Length', str(len(res)))
                self._write_buffer = [res]
                self._status_code = 200

            except Exception:
                self.log.exception('cannot write debug info')

        super(BaseHandler, self).flush(include_footers=False, **kwargs)

    def _log(self):
        super(BaseHandler, self)._log()
        self.log.stage_tag('flush')
        self.log.log_stages(self._status_code)

    # Preprocessors and postprocessors

    def _call_postprocessors(self, postprocessors, callback, *args):
        self._chain_functions(iter(postprocessors), callback, 'postprocessor', *args)

    def _chain_functions(self, functions, callback, chain_type, *args):
        try:
            func = next(functions)
            start_time = time.time()

            def _callback(*args):
                time_delta = (time.time() - start_time) * 1000
                self.log.debug('finished %s "%r" in %.2fms', chain_type, func, time_delta)
                self._chain_functions(functions, callback, chain_type, *args)

            func(self, *(args + (_callback,)))
        except StopIteration:
            callback(*args)

    @staticmethod
    def add_preprocessor(*preprocessors_list):
        def preprocessor_to_dependency(pp):
            @wraps(pp)
            def pp_replacement(handler):
                future = Future()

                def callback():
                    future.set_result(None)

                pp(handler, callback)
                return future

            return dependency(pp_replacement)

        return dependency([preprocessor_to_dependency(pp) for pp in preprocessors_list])

    def add_template_postprocessor(self, postprocessor):
        self._template_postprocessors.append(postprocessor)

    def add_early_postprocessor(self, postprocessor):
        self._early_postprocessors.append(postprocessor)

    def add_late_postprocessor(self, postprocessor):
        self._late_postprocessors.append(postprocessor)

    # Producers

    def _generic_producer(self, callback):
        self.log.debug('finishing plaintext')
        callback(self.text)

    # Deprecated, use self.text directly
    def set_plaintext_response(self, text):
        self.text = text

    def xml_from_file(self, filename):
        return self.xml_producer.xml_from_file(filename)

    def set_xsl(self, filename):
        return self.xml_producer.set_xsl(filename)

    def set_template(self, filename):
        return self.json_producer.set_template(filename)


class PageHandler(BaseHandler):
    def __init__(self, application, request, logger, request_id=None, **kwargs):
        super(PageHandler, self).__init__(application, request, logger, request_id, **kwargs)

    def group(self, futures, callback=None, name=None):
        return self._http_client.group(futures, callback, name)

    def get_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None, callback=None,
                follow_redirects=True, labels=None, add_to_finish_group=True,
                parse_response=True, parse_on_error=False):

        return self._http_client.get_url(
            url, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, follow_redirects=follow_redirects, labels=labels,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def head_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None, callback=None,
                 follow_redirects=True, labels=None, add_to_finish_group=True):

        return self._http_client.head_url(
            url, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, follow_redirects=follow_redirects, labels=labels,
            add_to_finish_group=add_to_finish_group
        )

    def post_url(self, url, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
                 callback=None, follow_redirects=True, content_type=None, labels=None,
                 add_to_finish_group=True, parse_response=True, parse_on_error=False):

        return self._http_client.post_url(
            url, data=data, headers=headers, files=files,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, follow_redirects=follow_redirects, content_type=content_type, labels=labels,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def put_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None, callback=None,
                content_type=None, labels=None, add_to_finish_group=True, parse_response=True, parse_on_error=False):

        return self._http_client.put_url(
            url, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, content_type=content_type, labels=labels,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def delete_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None, callback=None,
                   content_type=None, labels=None, add_to_finish_group=True, parse_response=True, parse_on_error=False):

        return self._http_client.delete_url(
            url, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, content_type=content_type, labels=labels,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )


class ErrorHandler(tornado.web.ErrorHandler, PageHandler):
    def initialize(self, status_code, logger=None):
        # Hides logger keyword argument from incompatible tornado versions
        super(ErrorHandler, self).initialize(status_code)


class RedirectHandler(tornado.web.RedirectHandler, PageHandler):
    def initialize(self, url, permanent=True, logger=None):
        # Hides logger keyword argument from incompatible tornado versions
        super(RedirectHandler, self).initialize(url, permanent)

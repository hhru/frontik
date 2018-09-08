# coding=utf-8

import time
from functools import partial

import tornado.curl_httpclient
import tornado.httputil
import tornado.options
import tornado.web
from tornado import gen
from tornado.concurrent import Future
from tornado.ioloop import IOLoop

import frontik.auth
import frontik.handler_active_limit
import frontik.producers.json_producer
import frontik.producers.xml_producer
import frontik.util
from frontik.futures import AsyncGroup
from frontik.compat import iteritems
from frontik.debug import DebugMode
from frontik.http_codes import process_status_code
from frontik.loggers.request import RequestLogger
from frontik.preprocessors import _get_preprocessors, _unwrap_preprocessors
from frontik.request_context import RequestContext
from frontik.util import raise_future_exception


class HTTPError(tornado.web.HTTPError):
    """Extends tornado.web.HTTPError with several keyword-only arguments and allows using
    some extended HTTP codes.

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


class DebugUnauthorizedHTTPError(HTTPError):
    pass


class BaseHandler(tornado.web.RequestHandler):

    preprocessors = ()

    def __init__(self, application, request, **kwargs):
        self._prepared = False
        self.name = self.__class__.__name__
        self.request_id = request.request_id = RequestContext.get('request_id')
        self.config = application.config
        self.log = RequestLogger(request)
        self.text = None

        self._exception_hooks = []

        for initializer in application.loggers_initializers:
            initializer(self)

        super(BaseHandler, self).__init__(application, request, **kwargs)

        self._debug_access = None
        self._page_aborted = False
        self._template_postprocessors = []
        self._postprocessors = []

        self._http_client = self.application.http_client_factory.get_http_client(self, self.modify_http_client_request)

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def prepare(self):
        self.active_limit = frontik.handler_active_limit.PageHandlerActiveLimit(self.request)
        self.debug_mode = DebugMode(self)
        self.finish_group = AsyncGroup(self.check_finished(self._finish_page_cb), name='finish')
        self._handler_finished_notification = self.finish_group.add_notification()

        self.json_producer = self.application.json.get_producer(self)
        self.json = self.json_producer.json

        self.xml_producer = self.application.xml.get_producer(self)
        self.doc = self.xml_producer.doc

        self._prepared = True

        super(BaseHandler, self).prepare()

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
                    raise DebugUnauthorizedHTTPError(code, headers=headers)

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

    def redirect(self, url, *args, **kwargs):
        self.log.info('redirecting to: %s', url)
        return super(BaseHandler, self).redirect(url, *args, **kwargs)

    def reverse_url(self, name, *args, **kwargs):
        return self.application.reverse_url(name, *args, **kwargs)

    @staticmethod
    def add_callback(callback, *args, **kwargs):
        IOLoop.current().add_callback(callback, *args, **kwargs)

    @staticmethod
    def add_timeout(deadline, callback, *args, **kwargs):
        return IOLoop.current().add_timeout(deadline, callback, *args, **kwargs)

    @staticmethod
    def remove_timeout(timeout):
        IOLoop.current().remove_timeout(timeout)

    @staticmethod
    def add_future(future, callback):
        IOLoop.current().add_future(future, callback)

    # Requests handling

    def _execute(self, transforms, *args, **kwargs):
        RequestContext.set('handler_name', repr(self))
        return super(BaseHandler, self)._execute(transforms, *args, **kwargs)

    def _execute_page_handler_after_preprocessor_completion(self, page_handler_method):
        self.log.stage_tag('prepare')
        wrapped_page_handler_method = self._create_handler_method_wrapper(page_handler_method)

        preprocessors = _unwrap_preprocessors(self.preprocessors) + _get_preprocessors(page_handler_method.__func__)
        self.add_future(self._run_preprocessors(preprocessors, self), wrapped_page_handler_method)

    @tornado.web.asynchronous
    def get(self, *args, **kwargs):
        self._execute_page_handler_after_preprocessor_completion(self.get_page)

    @tornado.web.asynchronous
    def post(self, *args, **kwargs):
        self._execute_page_handler_after_preprocessor_completion(self.post_page)

    @tornado.web.asynchronous
    def head(self, *args, **kwargs):
        self._execute_page_handler_after_preprocessor_completion(self.get_page)

    @tornado.web.asynchronous
    def delete(self, *args, **kwargs):
        self._execute_page_handler_after_preprocessor_completion(self.delete_page)

    @tornado.web.asynchronous
    def put(self, *args, **kwargs):
        self._execute_page_handler_after_preprocessor_completion(self.put_page)

    def options(self, *args, **kwargs):
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def _create_handler_method_wrapper(self, handler_method):
        def _handle_future(future):
            if future.exception():
                raise_future_exception(future)

            if not future.result():
                self.log.info('preprocessors chain was broken, skipping page method')
                return

            return_value = handler_method()

            if hasattr(self, 'handle_return_value'):
                method_name = handler_method.__name__
                self.handle_return_value(method_name, return_value)

            self._handler_finished_notification()

        return self.check_finished(_handle_future)

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

    def modify_http_client_request(self, balanced_request):
        pass

    # Finish page

    def is_finished(self):
        return self._finished

    def check_finished(self, callback, *args, **kwargs):
        original_callback = callback
        if args or kwargs:
            callback = partial(callback, *args, **kwargs)

        def wrapper(*args, **kwargs):
            if self._finished:
                self.log.warning('page was already finished, %s ignored', original_callback)
            else:
                return callback(*args, **kwargs)

        return wrapper

    def finish_with_postprocessors(self):
        self.finish_group.finish()

    def abort_preprocessors(self, wait_finish_group=True):
        self._page_aborted = True
        if wait_finish_group:
            self._handler_finished_notification()
        else:
            self.finish_with_postprocessors()

    def _finish_page_cb(self):
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

        self._call_postprocessors(self._postprocessors, _callback)

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
        """`send_error` is adapted to support `write_error` that can call
        `finish` asynchronously.
        """

        self.log.stage_tag('page')

        if self._headers_written:
            super(BaseHandler, self).send_error(status_code, **kwargs)

        self.clear()

        reason = kwargs.get('reason')
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
        """`write_error` can call `finish` asynchronously.
        This allows, for example, asynchronous templating on error pages.
        """

        if 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
        else:
            exception = None

        headers = getattr(exception, 'headers', None)
        override_content = any(getattr(exception, x, None) is not None for x in ('text', 'xml', 'json'))
        finish_with_exception = isinstance(exception, HTTPError) and override_content

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
        self.log.stage_tag('postprocess')

        if self._status_code in (204, 304) or (100 <= self._status_code < 200):
            chunk = None

        super(BaseHandler, self).finish(chunk)
        self.cleanup()

    # Preprocessors and postprocessors

    def add_to_preprocessors_group(self, future):
        return self.preprocessors_group.add_future(future)

    @gen.coroutine
    def _run_preprocessors(self, preprocessors, *args, **kwargs):
        self.preprocessors_group = AsyncGroup(lambda: None, name='preprocessors')
        preprocessors_group_notification = self.preprocessors_group.add_notification()

        for p in preprocessors:
            yield gen.coroutine(p)(*args, **kwargs)
            if self._finished or self._page_aborted:
                self.log.warning('page has already started finishing, breaking preprocessors chain')
                raise gen.Return(False)

        preprocessors_group_notification()
        yield self.preprocessors_group.get_finish_future()

        raise gen.Return(True)

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

    def add_template_postprocessor(self, postprocessor):
        self._template_postprocessors.append(postprocessor)

    def add_postprocessor(self, postprocessor):
        self._postprocessors.append(postprocessor)

    # Producers

    def _generic_producer(self, callback):
        self.log.debug('finishing plaintext')
        callback(self.text)

    def xml_from_file(self, filename):
        return self.xml_producer.xml_from_file(filename)

    def set_xsl(self, filename):
        return self.xml_producer.set_xsl(filename)

    def set_template(self, filename):
        return self.json_producer.set_template(filename)


class PageHandler(BaseHandler):
    def group(self, futures, callback=None, name=None):
        return self._http_client.group(futures, callback, name)

    def get_url(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
                max_timeout_tries=None, callback=None, follow_redirects=True,
                add_to_finish_group=True, parse_response=True, parse_on_error=False):

        return self._http_client.get_url(
            host, uri, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, callback=callback, follow_redirects=follow_redirects,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def head_url(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
                 max_timeout_tries=None, callback=None, follow_redirects=True, add_to_finish_group=True):

        return self._http_client.head_url(
            host, uri, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, callback=callback, follow_redirects=follow_redirects,
            add_to_finish_group=add_to_finish_group
        )

    def post_url(self, host, uri, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
                 max_timeout_tries=None, idempotent=False, callback=None, follow_redirects=True, content_type=None,
                 add_to_finish_group=True, parse_response=True, parse_on_error=False):

        return self._http_client.post_url(
            host, uri, data=data, headers=headers, files=files,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, idempotent=idempotent, callback=callback,
            follow_redirects=follow_redirects, content_type=content_type,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def put_url(self, host, uri, data='', headers=None, connect_timeout=None, request_timeout=None,
                max_timeout_tries=None, callback=None, content_type=None, add_to_finish_group=True,
                parse_response=True, parse_on_error=False):

        return self._http_client.put_url(
            host, uri, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, callback=callback, content_type=content_type,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def delete_url(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
                   max_timeout_tries=None, callback=None, content_type=None, add_to_finish_group=True,
                   parse_response=True, parse_on_error=False):

        return self._http_client.delete_url(
            host, uri, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, callback=callback, content_type=content_type,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )


class ErrorHandler(PageHandler, tornado.web.ErrorHandler):
    pass


class RedirectHandler(PageHandler, tornado.web.RedirectHandler):
    pass

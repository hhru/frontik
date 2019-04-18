import http.client
import logging
from functools import wraps

import tornado.curl_httpclient
import tornado.httputil
import tornado.web
from tornado import gen, stack_context
from tornado.ioloop import IOLoop
from tornado.options import options
from tornado.web import RequestHandler

import frontik.auth
import frontik.handler_active_limit
import frontik.producers.json_producer
import frontik.producers.xml_producer
import frontik.util
from frontik import media_types, request_context
from frontik.futures import AbortAsyncGroup, AsyncGroup
from frontik.debug import DebugMode
from frontik.http_client import FailFastError, RequestResult
from frontik.loggers.stages import StagesLogger
from frontik.preprocessors import _get_preprocessors, _unwrap_preprocessors
from frontik.version import version as frontik_version


def _fallback_status_code(status_code):
    return status_code if status_code in http.client.responses else http.client.SERVICE_UNAVAILABLE


class FinishWithPostprocessors(Exception):
    def __init__(self, wait_finish_group=False):
        self.wait_finish_group = wait_finish_group


class HTTPErrorWithPostprocessors(tornado.web.HTTPError):
    pass


handler_logger = logging.getLogger('handler')


class PageHandler(RequestHandler):

    preprocessors = ()

    def __init__(self, application, request, **kwargs):
        self.name = self.__class__.__name__
        self.request_id = request.request_id = request_context.get_request_id()
        self.config = application.config
        self.log = handler_logger
        self.text = None

        super().__init__(application, request, **kwargs)

        self._preprocessor_futures = []
        self._exception_hooks = []

        for integration in application.available_integrations:
            integration.initialize_handler(self)

        self.stages_logger = StagesLogger(request, self.statsd_client)

        self._debug_access = None
        self._render_postprocessors = []
        self._postprocessors = []

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def prepare(self):
        self._http_client = self.application.http_client_factory.get_http_client(self, self.modify_http_client_request)

        self.active_limit = frontik.handler_active_limit.ActiveHandlersLimit(self.statsd_client)
        self.debug_mode = DebugMode(self)
        self.finish_group = AsyncGroup(lambda: None, name='finish')
        self._handler_finished_notification = self.finish_group.add_notification()

        self.json_producer = self.application.json.get_producer(self)
        self.json = self.json_producer.json

        self.xml_producer = self.application.xml.get_producer(self)
        self.doc = self.xml_producer.doc

        super().prepare()

    def require_debug_access(self, login=None, passwd=None):
        if self._debug_access is None:
            if options.debug:
                debug_access = True
            else:
                check_login = login if login is not None else options.debug_login
                check_passwd = passwd if passwd is not None else options.debug_password
                frontik.auth.check_debug_auth(self, check_login, check_passwd)
                debug_access = True

            self._debug_access = debug_access

    def set_default_headers(self):
        self._headers = tornado.httputil.HTTPHeaders({
            'Server': f'Frontik/{frontik_version}',
            'X-Request-Id': self.request_id,
        })

    def decode_argument(self, value, name=None):
        try:
            return super().decode_argument(value, name)
        except (UnicodeError, tornado.web.HTTPError):
            self.log.warning('cannot decode utf-8 query parameter, trying other charsets')

        try:
            return frontik.util.decode_string_from_charset(value)
        except UnicodeError:
            self.log.exception('cannot decode argument, ignoring invalid chars')
            return value.decode('utf-8', 'ignore')

    def set_status(self, status_code, reason=None):
        status_code = _fallback_status_code(status_code)
        super().set_status(status_code, reason=reason)

    def redirect(self, url, *args, **kwargs):
        self.log.info('redirecting to: %s', url)
        return super().redirect(url, *args, **kwargs)

    def reverse_url(self, name, *args, **kwargs):
        return self.application.reverse_url(name, *args, **kwargs)

    @classmethod
    def add_callback(cls, callback, *args, **kwargs):
        IOLoop.current().add_callback(callback, *args, **kwargs)

    @classmethod
    def add_timeout(cls, deadline, callback, *args, **kwargs):
        return IOLoop.current().add_timeout(deadline, callback, *args, **kwargs)

    @staticmethod
    def remove_timeout(timeout):
        IOLoop.current().remove_timeout(timeout)

    @classmethod
    def add_future(cls, future, callback):
        IOLoop.current().add_future(future, callback)

    # Requests handling

    def _execute(self, transforms, *args, **kwargs):
        request_context.set_handler_name(repr(self))
        with stack_context.ExceptionStackContext(self._stack_context_handle_exception):
            return super()._execute(transforms, *args, **kwargs)

    @gen.coroutine
    def get(self, *args, **kwargs):
        yield self._execute_page(self.get_page)

    @gen.coroutine
    def post(self, *args, **kwargs):
        yield self._execute_page(self.post_page)

    @gen.coroutine
    def head(self, *args, **kwargs):
        yield self._execute_page(self.get_page)

    @gen.coroutine
    def delete(self, *args, **kwargs):
        yield self._execute_page(self.delete_page)

    @gen.coroutine
    def put(self, *args, **kwargs):
        yield self._execute_page(self.put_page)

    def options(self, *args, **kwargs):
        self.__return_405()

    @gen.coroutine
    def _execute_page(self, page_handler_method):
        self.stages_logger.commit_stage('prepare')

        preprocessors = _unwrap_preprocessors(self.preprocessors) + _get_preprocessors(page_handler_method.__func__)
        preprocessors_completed = yield self._run_preprocessors(preprocessors)

        if not preprocessors_completed:
            self.log.info('page was already finished, skipping page method')
            return

        yield gen.coroutine(page_handler_method)()

        self._handler_finished_notification()
        yield self.finish_group.get_finish_future()

        render_result = yield self._postprocess()
        if render_result is not None:
            self.write(render_result)

    def get_page(self):
        """ This method can be implemented in the subclass """
        self.__return_405()

    def post_page(self):
        """ This method can be implemented in the subclass """
        self.__return_405()

    def put_page(self):
        """ This method can be implemented in the subclass """
        self.__return_405()

    def delete_page(self):
        """ This method can be implemented in the subclass """
        self.__return_405()

    def __return_405(self):
        allowed_methods = [
            name for name in ('get', 'post', 'put', 'delete') if f'{name}_page' in vars(self.__class__)
        ]
        self.set_header('Allow', ', '.join(allowed_methods))
        self.set_status(405)
        self.finish()

    def get_page_fail_fast(self, request_result: RequestResult):
        self.__return_error(request_result.response.code)

    def post_page_fail_fast(self, request_result: RequestResult):
        self.__return_error(request_result.response.code)

    def put_page_fail_fast(self, request_result: RequestResult):
        self.__return_error(request_result.response.code)

    def delete_page_fail_fast(self, request_result: RequestResult):
        self.__return_error(request_result.response.code)

    def __return_error(self, response_code):
        self.send_error(response_code if 300 <= response_code < 500 else 502)

    # Finish page

    def is_finished(self):
        return self._finished

    def check_finished(self, callback):
        @wraps(callback)
        def wrapper(*args, **kwargs):
            if self._finished:
                self.log.warning('page was already finished, %s ignored', callback)
            else:
                return callback(*args, **kwargs)

        return wrapper

    def finish_with_postprocessors(self):
        if not self.finish_group.get_finish_future().done():
            self.finish_group.abort()

        def _cb(future):
            if future.result() is not None:
                self.finish(future.result())

        self.add_future(self._postprocess(), _cb)

    @gen.coroutine
    def _postprocess(self):
        if self._finished:
            self.log.info('page was already finished, skipping postprocessors')
            return

        postprocessors_completed = yield self._run_postprocessors(self._postprocessors)
        self.stages_logger.commit_stage('page')

        if not postprocessors_completed:
            self.log.info('page was already finished, skipping page producer')
            return

        if self.text is not None:
            renderer = self._generic_producer
        elif not self.json.is_empty():
            renderer = self.json_producer
        else:
            renderer = self.xml_producer

        self.log.debug('using %s renderer', renderer)
        rendered_result = yield renderer()

        postprocessed_result = yield self._run_template_postprocessors(self._render_postprocessors, rendered_result)
        return postprocessed_result

    def on_connection_close(self):
        self.finish_group.abort()
        self.stages_logger.commit_stage('page')
        self.stages_logger.flush_stages(408)
        self.cleanup()

    def on_finish(self):
        self.stages_logger.commit_stage('flush')
        self.stages_logger.flush_stages(self.get_status())

    def register_exception_hook(self, exception_hook):
        """
        Adds a function to the list of hooks, which are executed when `log_exception` is called.
        `exception_hook` must have the same signature as `log_exception`
        """
        self._exception_hooks.append(exception_hook)

    def log_exception(self, typ, value, tb):
        super().log_exception(typ, value, tb)

        for exception_hook in self._exception_hooks:
            exception_hook(typ, value, tb)

    def _handle_request_exception(self, e):
        if isinstance(e, AbortAsyncGroup):
            self.log.info('page was aborted, skipping postprocessing')

        elif isinstance(e, FinishWithPostprocessors):
            if e.wait_finish_group:
                self._handler_finished_notification()
                self.add_future(self.finish_group.get_finish_future(), lambda _: self.finish_with_postprocessors())
            else:
                self.finish_with_postprocessors()

        elif isinstance(e, FailFastError):
            response = e.failed_request.response
            request = e.failed_request.request

            if self.log.isEnabledFor(logging.WARNING):
                _max_uri_length = 24

                request_name = request.get_host() + request.uri[:_max_uri_length]
                if len(request.uri) > _max_uri_length:
                    request_name += '...'
                if request.name:
                    request_name = f'{request_name} ({request.name})'

                self.log.warning('FailFastError: request %s failed with %s code', request_name, response.code)

            try:
                error_method_name = f'{self.request.method.lower()}_page_fail_fast'
                method = getattr(self, error_method_name, None)
                if callable(method):
                    method(e.failed_request)
                else:
                    self.__return_error(e.failed_request.response.code)

            except Exception as exc:
                super()._handle_request_exception(exc)

        else:
            super()._handle_request_exception(e)

    def send_error(self, status_code=500, **kwargs):
        """`send_error` is adapted to support `write_error` that can call
        `finish` asynchronously.
        """

        self.stages_logger.commit_stage('page')

        if self._headers_written:
            super().send_error(status_code, **kwargs)
            return

        reason = kwargs.get('reason')
        if 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
            if isinstance(exception, tornado.web.HTTPError) and exception.reason:
                reason = exception.reason
        else:
            exception = None

        if not isinstance(exception, HTTPErrorWithPostprocessors):
            self.clear()

        self.set_status(status_code, reason=reason)

        try:
            self.write_error(status_code, **kwargs)
        except Exception:
            self.log.exception('Uncaught exception in write_error')
            if not self._finished:
                self.finish()

    def write_error(self, status_code=500, **kwargs):
        """
        `write_error` can call `finish` asynchronously if HTTPErrorWithPostprocessors is raised.
        """

        if 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
        else:
            exception = None

        if isinstance(exception, HTTPErrorWithPostprocessors):
            self.finish_with_postprocessors()
            return

        self.set_header('Content-Type', media_types.TEXT_HTML)
        return super().write_error(status_code, **kwargs)

    def cleanup(self):
        if hasattr(self, 'active_limit'):
            self.active_limit.release()

    def finish(self, chunk=None):
        self.stages_logger.commit_stage('postprocess')

        if self._status_code in (204, 304) or (100 <= self._status_code < 200):
            self._write_buffer = []
            chunk = None

        super().finish(chunk)
        self.cleanup()

    # Preprocessors and postprocessors

    def add_preprocessor_future(self, future):
        if self._preprocessor_futures is None:
            raise Exception(
                'preprocessors chain is already finished, calling add_preprocessor_future at this time is incorrect'
            )

        self._preprocessor_futures.append(future)
        return future

    @gen.coroutine
    def _run_preprocessors(self, preprocessors):
        for p in preprocessors:
            yield gen.coroutine(p)(self)
            if self._finished:
                self.log.info('page was already finished, breaking preprocessors chain')
                return False

        yield gen.multi(self._preprocessor_futures)

        self._preprocessor_futures = None

        if self._finished:
            self.log.info('page was already finished, breaking preprocessors chain')
            return False

        return True

    @gen.coroutine
    def _run_postprocessors(self, postprocessors):
        for p in postprocessors:
            yield gen.coroutine(p)(self)

            if self._finished:
                self.log.warning('page was already finished, breaking postprocessors chain')
                return False

        return True

    @gen.coroutine
    def _run_template_postprocessors(self, postprocessors, rendered_template):
        for p in postprocessors:
            rendered_template = yield gen.coroutine(p)(self, rendered_template)

            if self._finished:
                self.log.warning('page was already finished, breaking postprocessors chain')
                return None

        return rendered_template

    def add_render_postprocessor(self, postprocessor):
        self._render_postprocessors.append(postprocessor)

    def add_postprocessor(self, postprocessor):
        self._postprocessors.append(postprocessor)

    # Producers

    async def _generic_producer(self):
        self.log.debug('finishing plaintext')

        if self._headers.get('Content-Type') is None:
            self.set_header('Content-Type', media_types.TEXT_HTML)

        return self.text

    def xml_from_file(self, filename):
        return self.xml_producer.xml_from_file(filename)

    def set_xsl(self, filename):
        return self.xml_producer.set_xsl(filename)

    def set_template(self, filename):
        return self.json_producer.set_template(filename)

    # HTTP client methods

    def modify_http_client_request(self, balanced_request):
        pass

    def group(self, futures, callback=None, name=None):
        return self._http_client.group(futures, callback, name)

    def get_url(self, host, uri, *, name=None, data=None, headers=None, follow_redirects=True,
                connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                callback=None, add_to_finish_group=True, parse_response=True, parse_on_error=True, fail_fast=False):

        return self._http_client.get_url(
            host, uri, name=name, data=data, headers=headers, follow_redirects=follow_redirects,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, add_to_finish_group=add_to_finish_group, parse_response=parse_response,
            parse_on_error=parse_on_error, fail_fast=fail_fast
        )

    def head_url(self, host, uri, *, name=None, data=None, headers=None, follow_redirects=True,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                 callback=None, add_to_finish_group=True, fail_fast=False):

        return self._http_client.head_url(
            host, uri, data=data, name=name, headers=headers, follow_redirects=follow_redirects,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, add_to_finish_group=add_to_finish_group, fail_fast=fail_fast
        )

    def post_url(self, host, uri, *,
                 name=None, data='', headers=None, files=None, content_type=None, follow_redirects=True,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None, idempotent=False,
                 callback=None, add_to_finish_group=True, parse_response=True, parse_on_error=True,
                 fail_fast=False):

        return self._http_client.post_url(
            host, uri, data=data, name=name, headers=headers, files=files, content_type=content_type,
            follow_redirects=follow_redirects, connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, idempotent=idempotent, callback=callback,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error,
            fail_fast=fail_fast
        )

    def put_url(self, host, uri, *, name=None, data='', headers=None, content_type=None,
                connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                callback=None, add_to_finish_group=True, parse_response=True, parse_on_error=True, fail_fast=False):

        return self._http_client.put_url(
            host, uri, name=name, data=data, headers=headers, content_type=content_type,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, add_to_finish_group=add_to_finish_group, parse_response=parse_response,
            parse_on_error=parse_on_error, fail_fast=fail_fast
        )

    def delete_url(self, host, uri, *, name=None, data=None, headers=None, content_type=None,
                   connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                   callback=None, add_to_finish_group=True, parse_response=True, parse_on_error=True, fail_fast=False):

        return self._http_client.delete_url(
            host, uri, name=name, data=data, headers=headers, content_type=content_type,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, add_to_finish_group=add_to_finish_group, parse_response=parse_response,
            parse_on_error=parse_on_error, fail_fast=fail_fast
        )


class ErrorHandler(PageHandler, tornado.web.ErrorHandler):
    pass


class RedirectHandler(PageHandler, tornado.web.RedirectHandler):
    pass

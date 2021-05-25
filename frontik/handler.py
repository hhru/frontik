import http.client
import json
import logging
import re
import time
import math

from asyncio.futures import Future
from functools import partial, wraps
from typing import TYPE_CHECKING, Any, List, Type, Union

import tornado.curl_httpclient
import tornado.httputil
import tornado.web
from tornado import gen, stack_context
from tornado.ioloop import IOLoop
from tornado.options import options
from tornado.web import RequestHandler
from pydantic import ValidationError, BaseModel
from http_client import FailFastError, HttpClient, RequestResult, USER_AGENT_HEADER

import frontik.auth
import frontik.handler_active_limit
import frontik.producers.json_producer
import frontik.producers.xml_producer
import frontik.util
from frontik import media_types, request_context
from frontik.auth import DEBUG_AUTH_HEADER_NAME
from frontik.futures import AbortAsyncGroup, AsyncGroup
from frontik.debug import DEBUG_HEADER_NAME, DebugMode
from frontik.timeout_tracking import get_timeout_checker
from frontik.loggers.stages import StagesLogger
from frontik.preprocessors import _get_preprocessors, _unwrap_preprocessors, _get_preprocessor_name
from frontik.util import make_url
from frontik.version import version as frontik_version
from frontik.validator import BaseValidationModel, Validators

if TYPE_CHECKING:
    from http_client import BalancedHttpRequest


def _fallback_status_code(status_code):
    return status_code if status_code in http.client.responses else http.client.SERVICE_UNAVAILABLE


class FinishWithPostprocessors(Exception):
    def __init__(self, wait_finish_group=False):
        self.wait_finish_group = wait_finish_group


class HTTPErrorWithPostprocessors(tornado.web.HTTPError):
    pass


class TypedArgumentError(tornado.web.HTTPError):
    pass


class JSONBodyParseError(tornado.web.HTTPError):
    def __init__(self):
        super(JSONBodyParseError, self).__init__(400, 'Failed to parse json in request body')


class DefaultValueError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


_ARG_DEFAULT = object()
MEDIA_TYPE_PARAMETERS_SEPARATOR_RE = r' *; *'
OUTER_TIMEOUT_MS_HEADER = 'X-Outer-Timeout-Ms'

handler_logger = logging.getLogger('handler')


def _fail_fast_policy(fail_fast, waited, host, uri):
    if fail_fast and not waited:
        handler_logger.warning(
            'attempted to make NOT waited http request to %s %s with fail fast policy, turn off fail_fast',
            host, uri
        )
        return False

    return fail_fast


class PageHandler(RequestHandler):

    preprocessors = ()
    _priority_preprocessor_names = []

    def __init__(self, application, request, **kwargs):
        self.name = self.__class__.__name__
        self.request_id = request.request_id = request_context.get_request_id()
        self.config = application.config
        self.log = handler_logger
        self.text = None

        super().__init__(application, request, **kwargs)

        self._launched_preprocessors = []
        self._preprocessor_futures = []
        self._exception_hooks = []

        for integration in application.available_integrations:
            integration.initialize_handler(self)

        self.stages_logger = StagesLogger(request, self.statsd_client)

        self._debug_access = None
        self._render_postprocessors = []
        self._postprocessors = []

        self._mandatory_cookies = {}
        self._mandatory_headers = tornado.httputil.HTTPHeaders()

        self._validation_model = BaseValidationModel

        self.timeout_checker = None

        outer_timeout = request.headers.get(OUTER_TIMEOUT_MS_HEADER)
        if outer_timeout:
            self.timeout_checker = get_timeout_checker(request.headers.get(USER_AGENT_HEADER),
                                                       float(outer_timeout),
                                                       request.request_time)

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def prepare(self):
        self.active_limit = frontik.handler_active_limit.ActiveHandlersLimit(self.statsd_client)
        self.debug_mode = DebugMode(self)
        self.finish_group = AsyncGroup(lambda: None, name='finish')

        self.json_producer = self.application.json.get_producer(self)
        self.json = self.json_producer.json

        self.xml_producer = self.application.xml.get_producer(self)
        self.doc = self.xml_producer.doc

        self._http_client = self.application.http_client_factory.get_http_client(
            self.modify_http_client_request, self.debug_mode.enabled
        )  # type: HttpClient

        self._handler_finished_notification = self.finish_group.add_notification()

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

    def get_body_argument(self, name, default=_ARG_DEFAULT, strip=True):
        if self._get_request_mime_type(self.request) == media_types.APPLICATION_JSON:
            if name not in self.json_body and default == _ARG_DEFAULT:
                raise tornado.web.MissingArgumentError(name)

            result = self.json_body.get(name, default)

            if strip and isinstance(result, str):
                return result.strip()

            return result

        if default == _ARG_DEFAULT:
            return super().get_body_argument(name, strip=strip)
        return super().get_body_argument(name, default, strip)

    def set_validation_model(self, model: Type[Union[BaseValidationModel, BaseModel]]):
        if issubclass(model, BaseModel):
            self._validation_model = model
        else:
            raise TypeError('model is not subclass of BaseClass')

    def get_validated_argument(
        self, name: str, validation: Validators, default: any = _ARG_DEFAULT,
        from_body: bool = False, array: bool = False, strip: bool = True
    ) -> Any:
        validator = validation.value
        if default is not _ARG_DEFAULT:
            try:
                params = {validator: default}
                validated_default = self._validation_model(**params).dict().get(validator)
            except ValidationError:
                raise DefaultValueError
        else:
            validated_default = default

        if array and from_body:
            value = self.get_body_arguments(name, strip)
        elif from_body:
            value = self.get_body_argument(name, validated_default, strip)
        elif array:
            value = self.get_arguments(name, strip)
        else:
            value = self.get_argument(name, validated_default, strip)

        try:
            params = {validator: value}
            validated_value = self._validation_model(**params).dict().get(validator)
        except ValidationError:
            if default is _ARG_DEFAULT:
                raise TypedArgumentError(http.client.BAD_REQUEST, f'"{name}" argument is invalid')
            return default

        return validated_value

    def get_str_argument(
        self, name: str, default: str = _ARG_DEFAULT, path_safe: bool = True, **kwargs
    ) -> Union[str, List[str]]:
        if path_safe:
            return self.get_validated_argument(name, Validators.PATH_SAFE_STRING, default=default, **kwargs)
        return self.get_validated_argument(name, Validators.STRING, default=default, **kwargs)

    def get_int_argument(self, name: str, default: int = _ARG_DEFAULT, **kwargs) -> Union[int, List[int]]:
        return self.get_validated_argument(name, Validators.INTEGER, default=default, **kwargs)

    def get_bool_argument(self, name: str, default: bool = _ARG_DEFAULT, **kwargs) -> Union[bool, List[bool]]:
        return self.get_validated_argument(name, Validators.BOOLEAN, default=default, **kwargs)

    def get_float_argument(
        self, name: str, default: float = _ARG_DEFAULT, **kwargs
    ) -> Union[float, List[float]]:
        return self.get_validated_argument(name, Validators.FLOAT, default=default, **kwargs)

    def _get_request_mime_type(self, request):
        content_type = request.headers.get('Content-Type', '')
        return re.split(MEDIA_TYPE_PARAMETERS_SEPARATOR_RE, content_type)[0]

    def set_status(self, status_code, reason=None):
        status_code = _fallback_status_code(status_code)
        super().set_status(status_code, reason=reason)

    def redirect(self, url, *args, **kwargs):
        self.log.info('redirecting to: %s', url)
        return super().redirect(url, *args, **kwargs)

    def reverse_url(self, name, *args, **kwargs):
        return self.application.reverse_url(name, *args, **kwargs)

    @property
    def json_body(self):
        if not hasattr(self, '_json_body'):
            self._json_body = self._get_json_body()
        return self._json_body

    def _get_json_body(self):
        try:
            return json.loads(self.request.body)
        except json.JSONDecodeError as _:
            raise JSONBodyParseError()

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
        preprocessors = _get_preprocessors(page_handler_method.__func__)

        def _prioritise_preprocessor_by_list(preprocessor):
            name = _get_preprocessor_name(preprocessor)
            if name in self._priority_preprocessor_names:
                return self._priority_preprocessor_names.index(name)
            else:
                return math.inf

        preprocessors.sort(key=_prioritise_preprocessor_by_list)
        preprocessors_to_run = _unwrap_preprocessors(self.preprocessors) + preprocessors
        preprocessors_completed = yield self._run_preprocessors(preprocessors_to_run)

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
            if self.is_finished():
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
        rendered_result, meta_info = yield renderer()

        postprocessed_result = yield self._run_template_postprocessors(self._render_postprocessors,
                                                                       rendered_result, meta_info)
        return postprocessed_result

    def on_connection_close(self):
        super().on_connection_close()

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
        for name, value in self._mandatory_headers.items():
            self.set_header(name, value)

        for args, kwargs in self._mandatory_cookies.values():
            self.set_cookie(*args, **kwargs)

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

    def set_mandatory_header(self, name, value):
        self._mandatory_headers[name] = value

    def set_mandatory_cookie(self, name, value, domain=None, expires=None, path="/", expires_days=None, **kwargs):
        self._mandatory_cookies[name] = ((name, value, domain, expires, path, expires_days), kwargs)

    def clear_header(self, name):
        if name in self._mandatory_headers:
            del self._mandatory_headers[name]
        super().clear_header(name)

    def clear_cookie(self, name, path="/", domain=None):
        if name in self._mandatory_cookies:
            del self._mandatory_cookies[name]
        super().clear_cookie(name, path, domain)

    def was_preprocessor_called(self, preprocessor):
        return preprocessor.preprocessor_name in self._launched_preprocessors

    @gen.coroutine
    def _run_preprocessor_function(self, preprocessor_function):
        yield gen.coroutine(preprocessor_function)(self)
        self._launched_preprocessors.append(
            _get_preprocessor_name(preprocessor_function)
        )

    @gen.coroutine
    def run_preprocessor(self, preprocessor):
        if self._finished:
            self.log.info('page was already finished, cannot init preprocessor')
            return False
        yield self._run_preprocessor_function(preprocessor.function)

    @gen.coroutine
    def _run_preprocessors(self, preprocessor_functions):
        for p in preprocessor_functions:
            yield self._run_preprocessor_function(p)
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
    def _run_template_postprocessors(self, postprocessors, rendered_template, meta_info):
        for p in postprocessors:
            rendered_template = yield gen.coroutine(p)(self, rendered_template, meta_info)

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

        return self.text, None

    def xml_from_file(self, filename):
        return self.xml_producer.xml_from_file(filename)

    def set_xsl(self, filename):
        return self.xml_producer.set_xsl(filename)

    def set_template(self, filename):
        return self.json_producer.set_template(filename)

    # HTTP client methods

    def modify_http_client_request(self, balanced_request: 'BalancedHttpRequest'):
        balanced_request.headers['x-request-id'] = request_context.get_request_id()

        balanced_request.headers[OUTER_TIMEOUT_MS_HEADER] = f'{balanced_request.request_timeout * 1000:.0f}'

        if self.timeout_checker is not None:
            self.timeout_checker.check(balanced_request)

        if self.debug_mode.pass_debug:
            balanced_request.headers[DEBUG_HEADER_NAME] = 'true'

            # debug_timestamp is added to avoid caching of debug responses
            balanced_request.uri = make_url(balanced_request.uri, debug_timestamp=int(time.time()))

            for header_name in ('Authorization', DEBUG_AUTH_HEADER_NAME):
                authorization = self.request.headers.get(header_name)
                if authorization is not None:
                    balanced_request.headers[header_name] = authorization

    def group(self, futures, callback=None, name=None):
        group_future = Future()
        results_holder = {}

        def group_callback():
            if callable(callback):
                callback(results_holder)
            group_future.set_result(results_holder)

        def future_callback(name, future):
            results_holder[name] = future.result()

        async_group = AsyncGroup(self.finish_group.add(self.check_finished(group_callback)), name=name)

        for name, future in futures.items():
            if future.done():
                future_callback(name, future)
            else:
                self.add_future(future, async_group.add(partial(future_callback, name)))

        async_group.try_finish_async()

        return group_future

    def get_url(self, host, uri, *, name=None, data=None, headers=None, follow_redirects=True,
                connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                callback=None, waited=True, parse_response=True, parse_on_error=True, fail_fast=False):

        fail_fast = _fail_fast_policy(fail_fast, waited, host, uri)

        client_method = lambda callback: self._http_client.get_url(
            host, uri, name=name, data=data, headers=headers, follow_redirects=follow_redirects,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, parse_response=parse_response, parse_on_error=parse_on_error, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def head_url(self, host, uri, *, name=None, data=None, headers=None, follow_redirects=True,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                 callback=None, waited=True, fail_fast=False):

        fail_fast = _fail_fast_policy(fail_fast, waited, host, uri)

        client_method = lambda callback: self._http_client.head_url(
            host, uri, data=data, name=name, headers=headers, follow_redirects=follow_redirects,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def post_url(self, host, uri, *,
                 name=None, data='', headers=None, files=None, content_type=None, follow_redirects=True,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None, idempotent=False,
                 callback=None, waited=True, parse_response=True, parse_on_error=True, fail_fast=False):

        fail_fast = _fail_fast_policy(fail_fast, waited, host, uri)

        client_method = lambda callback: self._http_client.post_url(
            host, uri, data=data, name=name, headers=headers, files=files, content_type=content_type,
            follow_redirects=follow_redirects, connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, idempotent=idempotent,
            callback=callback, parse_response=parse_response, parse_on_error=parse_on_error, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def put_url(self, host, uri, *, name=None, data='', headers=None, content_type=None,
                connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                callback=None, waited=True, parse_response=True, parse_on_error=True, fail_fast=False):

        fail_fast = _fail_fast_policy(fail_fast, waited, host, uri)

        client_method = lambda callback: self._http_client.put_url(
            host, uri, name=name, data=data, headers=headers, content_type=content_type,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, parse_response=parse_response, parse_on_error=parse_on_error, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def delete_url(self, host, uri, *, name=None, data=None, headers=None, content_type=None,
                   connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                   callback=None, waited=True, parse_response=True, parse_on_error=True, fail_fast=False):

        fail_fast = _fail_fast_policy(fail_fast, waited, host, uri)

        client_method = lambda callback: self._http_client.delete_url(
            host, uri, name=name, data=data, headers=headers, content_type=content_type,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, parse_response=parse_response, parse_on_error=parse_on_error, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def _execute_http_client_method(self, host, uri, client_method, waited, callback):
        if waited and (self.is_finished() or self.finish_group.is_finished()):
            handler_logger.info(
                'attempted to make waited http request to %s %s in finished handler, ignoring', host, uri
            )

            future = Future()
            future.set_exception(AbortAsyncGroup())
            return future

        if waited and callable(callback):
            callback = self.check_finished(callback)

        future = client_method(callback)

        if waited:
            self.finish_group.add_future(future)

        return future


class ErrorHandler(PageHandler, tornado.web.ErrorHandler):
    pass


class RedirectHandler(PageHandler, tornado.web.RedirectHandler):
    def get_page(self):
        tornado.web.RedirectHandler.get(self)

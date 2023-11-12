from __future__ import annotations

import asyncio
import http.client
import json
import logging
import re
import time
from asyncio import Task
from asyncio.futures import Future
from functools import wraps
from typing import TYPE_CHECKING, Any

import tornado.httputil
import tornado.web
from http_client.request_response import USER_AGENT_HEADER, FailFastError, RequestBuilder, RequestResult
from pydantic import BaseModel, ValidationError
from tornado.ioloop import IOLoop
from tornado.web import Finish, RequestHandler

import frontik.auth
import frontik.handler_active_limit
import frontik.producers.json_producer
import frontik.producers.xml_producer
import frontik.util
from frontik import media_types, request_context
from frontik.auth import DEBUG_AUTH_HEADER_NAME
from frontik.debug import DEBUG_HEADER_NAME, DebugMode
from frontik.dependency_manager import execute_page_method_with_dependencies
from frontik.futures import AbortAsyncGroup, AsyncGroup
from frontik.http_status import ALLOWED_STATUSES, CLIENT_CLOSED_REQUEST
from frontik.loggers.stages import StagesLogger
from frontik.options import options
from frontik.timeout_tracking import get_timeout_checker
from frontik.util import gather_dict, make_url
from frontik.validator import BaseValidationModel, Validators
from frontik.version import version as frontik_version

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterable

    from http_client import HttpClient
    from tornado.httputil import HTTPServerRequest

    from frontik.app import FrontikApplication
    from frontik.integrations.statsd import StatsDClient, StatsDClientStub


def _fallback_status_code(status_code: int) -> int:
    return status_code if status_code in ALLOWED_STATUSES else http.client.SERVICE_UNAVAILABLE


class FinishWithPostprocessors(Exception):
    def __init__(self, wait_finish_group: bool = False) -> None:
        self.wait_finish_group = wait_finish_group


class HTTPErrorWithPostprocessors(tornado.web.HTTPError):
    pass


class TypedArgumentError(tornado.web.HTTPError):
    pass


class JSONBodyParseError(tornado.web.HTTPError):
    def __init__(self) -> None:
        super().__init__(400, 'Failed to parse json in request body')


class DefaultValueError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


_ARG_DEFAULT = object()
MEDIA_TYPE_PARAMETERS_SEPARATOR_RE = r' *; *'
OUTER_TIMEOUT_MS_HEADER = 'X-Outer-Timeout-Ms'

handler_logger = logging.getLogger('handler')


def _fail_fast_policy(fail_fast: bool, waited: bool, host: str, path: str) -> bool:
    if fail_fast and not waited:
        handler_logger.warning(
            'attempted to make NOT waited http request to %s %s with fail fast policy, turn off fail_fast',
            host,
            path,
        )
        return False

    return fail_fast


class PageHandler(RequestHandler):
    dependencies: Iterable = ()
    _priority_dependency_names: list[str] = []

    def __init__(self, application: FrontikApplication, request: HTTPServerRequest, **kwargs: Any) -> None:
        self.name = self.__class__.__name__
        self.request_id: str = request_context.get_request_id()  # type: ignore
        request.request_id = self.request_id  # type: ignore
        self.config = application.config
        self.log = handler_logger
        self.text: Any = None

        super().__init__(application, request, **kwargs)

        self._exception_hooks: list = []
        self.statsd_client: StatsDClient | StatsDClientStub

        for integration in application.available_integrations:
            integration.initialize_handler(self)

        self.stages_logger = StagesLogger(request, self.statsd_client)

        self._debug_access: bool | None = None
        self._render_postprocessors: list = []
        self._postprocessors: list = []

        self._mandatory_cookies: dict = {}
        self._mandatory_headers = tornado.httputil.HTTPHeaders()

        self._validation_model: type[BaseValidationModel | BaseModel] = BaseValidationModel

        self.timeout_checker = None
        self.use_adaptive_strategy = False
        outer_timeout = request.headers.get(OUTER_TIMEOUT_MS_HEADER)
        if outer_timeout:
            self.timeout_checker = get_timeout_checker(
                request.headers.get(USER_AGENT_HEADER),
                float(outer_timeout),
                request.request_time,
            )

    def __repr__(self):
        return f'{self.__module__}.{self.__class__.__name__}'

    def prepare(self) -> None:
        self.application: FrontikApplication
        self.active_limit = frontik.handler_active_limit.ActiveHandlersLimit(self.statsd_client)
        self.debug_mode = DebugMode(self)
        self.finish_group = AsyncGroup(lambda: None, name='finish')

        self.json_producer = self.application.json.get_producer(self)
        self.json = self.json_producer.json

        self.xml_producer = self.application.xml.get_producer(self)
        self.doc = self.xml_producer.doc

        self._http_client: HttpClient = self.application.http_client_factory.get_http_client(
            self.modify_http_client_request,
            self.debug_mode.enabled,
            self.use_adaptive_strategy,
        )

        self._handler_finished_notification = self.finish_group.add_notification()

        super().prepare()

    def require_debug_access(self, login: str | None = None, passwd: str | None = None) -> None:
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
        self._headers = tornado.httputil.HTTPHeaders(
            {
                'Server': f'Frontik/{frontik_version}',  # type: ignore
                'X-Request-Id': self.request_id,  # type: ignore
            },
        )

    def decode_argument(self, value: bytes, name: str | None = None) -> str:
        try:
            return super().decode_argument(value, name)
        except (UnicodeError, tornado.web.HTTPError):
            self.log.warning('cannot decode utf-8 query parameter, trying other charsets')

        try:
            return frontik.util.decode_string_from_charset(value)
        except UnicodeError:
            self.log.exception('cannot decode argument, ignoring invalid chars')
            return value.decode('utf-8', 'ignore')

    def get_body_argument(self, name: str, default: Any = _ARG_DEFAULT, strip: bool = True) -> str | None:
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

    def set_validation_model(self, model: type[BaseValidationModel | BaseModel]) -> None:
        if issubclass(model, BaseModel):
            self._validation_model = model
        else:
            msg = 'model is not subclass of BaseClass'
            raise TypeError(msg)

    def get_validated_argument(
        self,
        name: str,
        validation: Validators,
        default: Any = _ARG_DEFAULT,
        from_body: bool = False,
        array: bool = False,
        strip: bool = True,
    ) -> Any:
        validator = validation.value
        if default is not _ARG_DEFAULT and default is not None:
            try:
                params = {validator: default}
                validated_default = self._validation_model(**params).dict().get(validator)
            except ValidationError:
                raise DefaultValueError()
        else:
            validated_default = default

        value: Any
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
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        path_safe: bool = True,
        **kwargs: Any,
    ) -> str | list[str] | None:
        if path_safe:
            return self.get_validated_argument(name, Validators.PATH_SAFE_STRING, default=default, **kwargs)
        return self.get_validated_argument(name, Validators.STRING, default=default, **kwargs)

    def get_int_argument(
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        **kwargs: Any,
    ) -> int | list[int] | None:
        return self.get_validated_argument(name, Validators.INTEGER, default=default, **kwargs)

    def get_bool_argument(
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        **kwargs: Any,
    ) -> bool | list[bool] | None:
        return self.get_validated_argument(name, Validators.BOOLEAN, default=default, **kwargs)

    def get_float_argument(
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        **kwargs: Any,
    ) -> float | list[float] | None:
        return self.get_validated_argument(name, Validators.FLOAT, default=default, **kwargs)

    def _get_request_mime_type(self, request: HTTPServerRequest) -> str:
        content_type = request.headers.get('Content-Type', '')
        return re.split(MEDIA_TYPE_PARAMETERS_SEPARATOR_RE, content_type)[0]

    def set_status(self, status_code: int, reason: str | None = None) -> None:
        status_code = _fallback_status_code(status_code)
        super().set_status(status_code, reason=reason)

    def redirect(self, url, *args, allow_protocol_relative=False, **kwargs):
        if not allow_protocol_relative and url.startswith('//'):
            # A redirect with two initial slashes is a "protocol-relative" URL.
            # This means the next path segment is treated as a hostname instead
            # of a part of the path, making this effectively an open redirect.
            # Reject paths starting with two slashes to prevent this.
            # This is only reachable under certain configurations.
            raise tornado.web.HTTPError(403, 'cannot redirect path with two initial slashes')
        self.log.info('redirecting to: %s', url)
        return super().redirect(url, *args, **kwargs)

    def reverse_url(self, name: str, *args: Any, **kwargs: Any) -> str:
        return self.application.reverse_url(name, *args, **kwargs)

    @property
    def json_body(self):
        if not hasattr(self, '_json_body'):
            self._json_body = self._get_json_body()
        return self._json_body

    def _get_json_body(self) -> Any:
        try:
            return json.loads(self.request.body)
        except json.JSONDecodeError as _:
            raise JSONBodyParseError()

    @classmethod
    def add_callback(cls, callback: Callable, *args: Any, **kwargs: Any) -> None:
        IOLoop.current().add_callback(callback, *args, **kwargs)

    @classmethod
    def add_timeout(cls, deadline: float, callback: Callable, *args: Any, **kwargs: Any) -> Any:
        return IOLoop.current().add_timeout(deadline, callback, *args, **kwargs)

    @staticmethod
    def remove_timeout(timeout):
        IOLoop.current().remove_timeout(timeout)

    @classmethod
    def add_future(cls, future: Future, callback: Callable) -> None:
        IOLoop.current().add_future(future, callback)

    # Requests handling

    async def _execute(self, transforms, *args, **kwargs):
        request_context.set_handler_name(repr(self))
        try:
            return await super()._execute(transforms, *args, **kwargs)
        except Exception as ex:
            self._handle_request_exception(ex)
            return True

    async def get(self, *args, **kwargs):
        await self._execute_page(self.get_page)

    async def post(self, *args, **kwargs):
        await self._execute_page(self.post_page)

    async def put(self, *args, **kwargs):
        await self._execute_page(self.put_page)

    async def delete(self, *args, **kwargs):
        await self._execute_page(self.delete_page)

    async def head(self, *args, **kwargs):
        await self._execute_page(self.get_page)

    def options(self, *args, **kwargs):
        self.__return_405()

    async def _execute_page(self, page_handler_method: Callable[[], Coroutine[Any, Any, None]]) -> None:
        self.stages_logger.commit_stage('prepare')

        await execute_page_method_with_dependencies(self, page_handler_method)

        self._handler_finished_notification()
        await self.finish_group.get_gathering_future()
        await self.finish_group.get_finish_future()

        render_result = await self._postprocess()
        if render_result is not None:
            self.write(render_result)

    async def get_page(self):
        """This method can be implemented in the subclass"""
        self.__return_405()

    async def post_page(self):
        """This method can be implemented in the subclass"""
        self.__return_405()

    async def put_page(self):
        """This method can be implemented in the subclass"""
        self.__return_405()

    async def delete_page(self):
        """This method can be implemented in the subclass"""
        self.__return_405()

    def __return_405(self) -> None:
        allowed_methods = [name for name in ('get', 'post', 'put', 'delete') if f'{name}_page' in vars(self.__class__)]
        self.set_header('Allow', ', '.join(allowed_methods))
        self.set_status(405)
        self.finish()

    def get_page_fail_fast(self, request_result: RequestResult) -> None:
        self.__return_error(request_result.status_code, error_info={'is_fail_fast': True})

    def post_page_fail_fast(self, request_result: RequestResult) -> None:
        self.__return_error(request_result.status_code, error_info={'is_fail_fast': True})

    def put_page_fail_fast(self, request_result: RequestResult) -> None:
        self.__return_error(request_result.status_code, error_info={'is_fail_fast': True})

    def delete_page_fail_fast(self, request_result: RequestResult) -> None:
        self.__return_error(request_result.status_code, error_info={'is_fail_fast': True})

    def __return_error(self, response_code: int, **kwargs: Any) -> None:
        self.send_error(response_code if 300 <= response_code < 500 else 502, **kwargs)

    # Finish page

    def is_finished(self) -> bool:
        return self._finished

    def check_finished(self, callback: Callable) -> Callable:
        @wraps(callback)
        def wrapper(*args, **kwargs):
            if self.is_finished():
                self.log.warning('page was already finished, %s ignored', callback)
            else:
                return callback(*args, **kwargs)

        return wrapper

    def finish_with_postprocessors(self) -> None:
        if not self.finish_group.get_finish_future().done():
            self.finish_group.abort()

        def _cb(future):
            if future.result() is not None:
                self.finish(future.result())

        asyncio.create_task(self._postprocess()).add_done_callback(_cb)

    def run_task(self: PageHandler, coro: Coroutine) -> Task:
        task = asyncio.create_task(coro)
        self.finish_group.add_future(task)
        return task

    async def _postprocess(self) -> Any:
        if self._finished:
            self.log.info('page was already finished, skipping postprocessors')
            return

        postprocessors_completed = await self._run_postprocessors(self._postprocessors)
        self.stages_logger.commit_stage('page')

        if not postprocessors_completed:
            self.log.info('page was already finished, skipping page producer')
            return

        renderer: Any
        if self.text is not None:
            renderer = self._generic_producer
        elif not self.json.is_empty():
            renderer = self.json_producer
        else:
            renderer = self.xml_producer

        self.log.debug('using %s renderer', renderer)
        rendered_result, meta_info = await renderer()

        postprocessed_result = await self._run_template_postprocessors(
            self._render_postprocessors,
            rendered_result,
            meta_info,
        )
        return postprocessed_result

    def on_connection_close(self):
        token = request_context.initialize(self.request, self.request_id)
        try:
            super().on_connection_close()

            self.finish_group.abort()
            self.set_status(CLIENT_CLOSED_REQUEST, 'Client closed the connection: aborting request')

            self.stages_logger.commit_stage('page')
            self.stages_logger.flush_stages(self.get_status())

            self.finish()
        finally:
            request_context.reset(token)

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
        for exception_hook in self._exception_hooks:
            exception_hook(typ, value, tb)

        super().log_exception(typ, value, tb)

    def _handle_request_exception(self, e: BaseException) -> None:
        if isinstance(e, AbortAsyncGroup):
            self.log.info('page was aborted, skipping postprocessing')
            return

        if isinstance(e, FinishWithPostprocessors):
            if e.wait_finish_group:
                self._handler_finished_notification()
                self.add_future(self.finish_group.get_finish_future(), lambda _: self.finish_with_postprocessors())
            else:
                self.finish_with_postprocessors()
            return

        if self._finished and not isinstance(e, Finish):
            # tornado will handle Finish by itself
            # any other errors can't complete after handler is finished
            return

        if isinstance(e, FailFastError):
            request = e.failed_result.request

            if self.log.isEnabledFor(logging.WARNING):
                _max_uri_length = 24

                request_name = request.host + request.path[:_max_uri_length]
                if len(request.path) > _max_uri_length:
                    request_name += '...'
                if request.name:
                    request_name = f'{request_name} ({request.name})'

                self.log.warning(
                    'FailFastError: request %s failed with %s code',
                    request_name,
                    e.failed_result.status_code,
                )

            try:
                error_method_name = f'{self.request.method.lower()}_page_fail_fast'  # type: ignore
                method = getattr(self, error_method_name, None)
                if callable(method):
                    method(e.failed_result)
                else:
                    self.__return_error(e.failed_result.status_code, error_info={'is_fail_fast': True})

            except Exception as exc:
                super()._handle_request_exception(exc)

        else:
            super()._handle_request_exception(e)

    def send_error(self, status_code: int = 500, **kwargs: Any) -> None:
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

    def write_error(self, status_code: int = 500, **kwargs: Any) -> None:
        """
        `write_error` can call `finish` asynchronously if HTTPErrorWithPostprocessors is raised.
        """

        exception = kwargs['exc_info'][1] if 'exc_info' in kwargs else None

        if isinstance(exception, HTTPErrorWithPostprocessors):
            self.finish_with_postprocessors()
            return

        self.set_header('Content-Type', media_types.TEXT_HTML)
        super().write_error(status_code, **kwargs)

    def cleanup(self) -> None:
        if hasattr(self, 'active_limit'):
            self.active_limit.release()

    def finish(self, chunk: str | bytes | dict | None = None) -> Future[None]:
        self.stages_logger.commit_stage('postprocess')
        for name, value in self._mandatory_headers.items():
            self.set_header(name, value)

        for args, kwargs in self._mandatory_cookies.values():
            try:
                self.set_cookie(*args, **kwargs)
            except ValueError:
                self.set_status(http.client.BAD_REQUEST)

        if self._status_code in (204, 304) or (100 <= self._status_code < 200):
            self._write_buffer = []
            chunk = None

        finish_future = super().finish(chunk)
        self.cleanup()
        return finish_future

    # postprocessors

    def set_mandatory_header(self, name: str, value: str) -> None:
        self._mandatory_headers[name] = value

    def set_mandatory_cookie(
        self,
        name: str,
        value: str,
        domain: str | None = None,
        expires: str | None = None,
        path: str = "/",
        expires_days: int | None = None,
        **kwargs: Any,
    ) -> None:
        self._mandatory_cookies[name] = ((name, value, domain, expires, path, expires_days), kwargs)

    def clear_header(self, name: str) -> None:
        if name in self._mandatory_headers:
            del self._mandatory_headers[name]
        super().clear_header(name)

    def clear_cookie(self, name: str, path: str = "/", domain: str | None = None) -> None:  # type: ignore
        if name in self._mandatory_cookies:
            del self._mandatory_cookies[name]
        super().clear_cookie(name, path=path, domain=domain)

    async def _run_postprocessors(self, postprocessors: list) -> bool:
        for p in postprocessors:
            if asyncio.iscoroutinefunction(p):
                await p(self)
            else:
                p(self)

            if self._finished:
                self.log.warning('page was already finished, breaking postprocessors chain')
                return False

        return True

    async def _run_template_postprocessors(self, postprocessors: list, rendered_template: Any, meta_info: Any) -> Any:
        for p in postprocessors:
            if asyncio.iscoroutinefunction(p):
                rendered_template = await p(self, rendered_template, meta_info)
            else:
                rendered_template = p(self, rendered_template, meta_info)

            if self._finished:
                self.log.warning('page was already finished, breaking postprocessors chain')
                return None

        return rendered_template

    def add_render_postprocessor(self, postprocessor: Any) -> None:
        self._render_postprocessors.append(postprocessor)

    def add_postprocessor(self, postprocessor: Any) -> None:
        self._postprocessors.append(postprocessor)

    # Producers

    async def _generic_producer(self):
        self.log.debug('finishing plaintext')

        if self._headers.get('Content-Type') is None:
            self.set_header('Content-Type', media_types.TEXT_HTML)

        return self.text, None

    def xml_from_file(self, filename: str) -> Any:
        return self.xml_producer.xml_from_file(filename)

    def set_xsl(self, filename: str) -> None:
        self.xml_producer.set_xsl(filename)

    def set_template(self, filename: str) -> None:
        self.json_producer.set_template(filename)

    # HTTP client methods

    def modify_http_client_request(self, balanced_request: RequestBuilder) -> None:
        balanced_request.headers['x-request-id'] = request_context.get_request_id()

        balanced_request.headers[OUTER_TIMEOUT_MS_HEADER] = f'{balanced_request.request_timeout * 1000:.0f}'

        if self.timeout_checker is not None:
            self.timeout_checker.check(balanced_request)

        if self.debug_mode.pass_debug:
            balanced_request.headers[DEBUG_HEADER_NAME] = 'true'

            # debug_timestamp is added to avoid caching of debug responses
            balanced_request.path = make_url(balanced_request.path, debug_timestamp=int(time.time()))

            for header_name in ('Authorization', DEBUG_AUTH_HEADER_NAME):
                authorization = self.request.headers.get(header_name)
                if authorization is not None:
                    balanced_request.headers[header_name] = authorization

    def group(self, futures: dict) -> Task:
        return self.run_task(gather_dict(coro_dict=futures))

    def get_url(
        self,
        host: str,
        path: str,
        *,
        name: str | None = None,
        data: Any = None,
        headers: Any = None,
        follow_redirects: bool = True,
        profile: str | None = None,
        connect_timeout: float | None = None,
        request_timeout: float | None = None,
        max_timeout_tries: int | None = None,
        speculative_timeout_pct: float | None = None,
        waited: bool = True,
        parse_response: bool = True,
        parse_on_error: bool = True,
        fail_fast: bool = False,
    ) -> Future[RequestResult]:
        fail_fast = _fail_fast_policy(fail_fast, waited, host, path)

        def client_method():
            return self._http_client.get_url(
                host,
                path,
                name=name,
                data=data,
                headers=headers,
                follow_redirects=follow_redirects,
                profile=profile,
                connect_timeout=connect_timeout,
                request_timeout=request_timeout,
                max_timeout_tries=max_timeout_tries,
                speculative_timeout_pct=speculative_timeout_pct,
                parse_response=parse_response,
                parse_on_error=parse_on_error,
                fail_fast=fail_fast,
            )

        return self._execute_http_client_method(host, path, client_method, waited)

    def head_url(
        self,
        host: str,
        path: str,
        *,
        name: str | None = None,
        data: Any = None,
        headers: Any = None,
        follow_redirects: bool = True,
        profile: str | None = None,
        connect_timeout: float | None = None,
        request_timeout: float | None = None,
        max_timeout_tries: int | None = None,
        speculative_timeout_pct: float | None = None,
        waited: bool = True,
        fail_fast: bool = False,
    ) -> Future[RequestResult]:
        fail_fast = _fail_fast_policy(fail_fast, waited, host, path)

        def client_method():
            return self._http_client.head_url(
                host,
                path,
                data=data,
                name=name,
                headers=headers,
                follow_redirects=follow_redirects,
                profile=profile,
                connect_timeout=connect_timeout,
                request_timeout=request_timeout,
                max_timeout_tries=max_timeout_tries,
                speculative_timeout_pct=speculative_timeout_pct,
                fail_fast=fail_fast,
            )

        return self._execute_http_client_method(host, path, client_method, waited)

    def post_url(
        self,
        host: str,
        path: str,
        *,
        name: str | None = None,
        data: Any = '',
        headers: Any = None,
        files: Any = None,
        content_type: str | None = None,
        follow_redirects: bool | None = True,
        profile: str | None = None,
        connect_timeout: float | None = None,
        request_timeout: float | None = None,
        max_timeout_tries: int | None = None,
        idempotent: bool = False,
        speculative_timeout_pct: float | None = None,
        waited: bool = True,
        parse_response: bool = True,
        parse_on_error: bool = True,
        fail_fast: bool = False,
    ) -> Future[RequestResult]:
        fail_fast = _fail_fast_policy(fail_fast, waited, host, path)

        def client_method():
            return self._http_client.post_url(
                host,
                path,
                data=data,
                name=name,
                headers=headers,
                files=files,
                content_type=content_type,
                follow_redirects=follow_redirects,
                profile=profile,
                connect_timeout=connect_timeout,
                request_timeout=request_timeout,
                max_timeout_tries=max_timeout_tries,
                idempotent=idempotent,
                speculative_timeout_pct=speculative_timeout_pct,
                parse_response=parse_response,
                parse_on_error=parse_on_error,
                fail_fast=fail_fast,
            )

        return self._execute_http_client_method(host, path, client_method, waited)

    def put_url(
        self,
        host: str,
        path: str,
        *,
        name: str | None = None,
        data: Any = '',
        headers: Any = None,
        content_type: str | None = None,
        follow_redirects: bool = True,
        profile: str | None = None,
        connect_timeout: float | None = None,
        request_timeout: float | None = None,
        max_timeout_tries: int | None = None,
        idempotent: bool = True,
        speculative_timeout_pct: float | None = None,
        waited: bool = True,
        parse_response: bool = True,
        parse_on_error: bool = True,
        fail_fast: bool = False,
    ) -> Future[RequestResult]:
        fail_fast = _fail_fast_policy(fail_fast, waited, host, path)

        def client_method():
            return self._http_client.put_url(
                host,
                path,
                name=name,
                data=data,
                headers=headers,
                content_type=content_type,
                follow_redirects=follow_redirects,
                profile=profile,
                connect_timeout=connect_timeout,
                request_timeout=request_timeout,
                max_timeout_tries=max_timeout_tries,
                idempotent=idempotent,
                speculative_timeout_pct=speculative_timeout_pct,
                parse_response=parse_response,
                parse_on_error=parse_on_error,
                fail_fast=fail_fast,
            )

        return self._execute_http_client_method(host, path, client_method, waited)

    def delete_url(
        self,
        host: str,
        path: str,
        *,
        name: str | None = None,
        data: Any = None,
        headers: Any = None,
        content_type: str | None = None,
        profile: str | None = None,
        connect_timeout: float | None = None,
        request_timeout: float | None = None,
        max_timeout_tries: int | None = None,
        speculative_timeout_pct: float | None = None,
        waited: bool = True,
        parse_response: bool = True,
        parse_on_error: bool = True,
        fail_fast: bool = False,
    ) -> Future[RequestResult]:
        fail_fast = _fail_fast_policy(fail_fast, waited, host, path)

        def client_method():
            return self._http_client.delete_url(
                host,
                path,
                name=name,
                data=data,
                headers=headers,
                content_type=content_type,
                profile=profile,
                connect_timeout=connect_timeout,
                request_timeout=request_timeout,
                max_timeout_tries=max_timeout_tries,
                parse_response=parse_response,
                parse_on_error=parse_on_error,
                speculative_timeout_pct=speculative_timeout_pct,
                fail_fast=fail_fast,
            )

        return self._execute_http_client_method(host, path, client_method, waited)

    def _execute_http_client_method(
        self,
        host: str,
        path: str,
        client_method: Callable,
        waited: bool,
    ) -> Future[RequestResult]:
        if waited and (self.is_finished() or self.finish_group.is_finished()):
            handler_logger.info(
                'attempted to make waited http request to %s %s in finished handler, ignoring',
                host,
                path,
            )

            future: Future = Future()
            future.set_exception(AbortAsyncGroup())
            return future

        future = client_method()

        if waited:
            self.finish_group.add_future(future)

        return future


class ErrorHandler(PageHandler, tornado.web.ErrorHandler):
    pass


class RedirectHandler(PageHandler, tornado.web.RedirectHandler):
    def get_page(self):
        tornado.web.RedirectHandler.get(self)

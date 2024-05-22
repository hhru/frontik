from __future__ import annotations

import asyncio
import datetime
import http.client
import json
import logging
import re
import sys
import time
from asyncio import Task
from asyncio.futures import Future
from typing import TYPE_CHECKING, Any, Optional, Type, TypeVar, Union, overload

from fastapi import Depends, HTTPException, Request, Response
from fastapi.routing import APIRoute
from http_client.request_response import USER_AGENT_HEADER, FailFastError, RequestBuilder, RequestResult
from pydantic import BaseModel, ValidationError
from starlette.datastructures import Headers, QueryParams
from tornado.httputil import format_timestamp, parse_body_arguments

import frontik.auth
import frontik.handler_active_limit
import frontik.producers.json_producer
import frontik.producers.xml_producer
import frontik.util
from frontik import media_types, request_context
from frontik.auth import DEBUG_AUTH_HEADER_NAME
from frontik.debug import DEBUG_HEADER_NAME, DebugMode, DebugTransform
from frontik.futures import AbortAsyncGroup, AsyncGroup
from frontik.http_status import ALLOWED_STATUSES
from frontik.json_builder import FrontikJsonDecodeError, json_decode
from frontik.loggers import CUSTOM_JSON_EXTRA, JSON_REQUESTS_LOGGER
from frontik.loggers.stages import StagesLogger
from frontik.options import options
from frontik.timeout_tracking import get_timeout_checker
from frontik.util import make_url
from frontik.validator import BaseValidationModel, Validators
from frontik.version import version as frontik_version

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from http_client import HttpClient

    from frontik.app import FrontikApplication
    from frontik.integrations.statsd import StatsDClient, StatsDClientStub


class FinishWithPostprocessors(Exception):
    def __init__(self, wait_finish_group: bool = False) -> None:
        self.wait_finish_group = wait_finish_group


class HTTPErrorWithPostprocessors(HTTPException):
    pass


class TypedArgumentError(HTTPException):
    pass


class JSONBodyParseError(HTTPException):
    def __init__(self) -> None:
        super().__init__(400, 'Failed to parse json in request body')


class DefaultValueError(HTTPException):
    def __init__(self, arg_name: str) -> None:
        super().__init__(400, 'Missing argument %s' % arg_name)
        self.arg_name = arg_name


class FinishPageSignal(Exception):
    def __init__(self, data: Any = None, *args: object) -> None:
        super().__init__(*args)
        self.data = data


class RedirectPageSignal(Exception):
    def __init__(self, url: str, status: int, *args: object) -> None:
        super().__init__(*args)
        self.url = url
        self.status = status


_ARG_DEFAULT = object()
MEDIA_TYPE_PARAMETERS_SEPARATOR_RE = r' *; *'
OUTER_TIMEOUT_MS_HEADER = 'X-Outer-Timeout-Ms'
_remove_control_chars_regex = re.compile(r'[\x00-\x08\x0e-\x1f]')
_T = TypeVar('_T')

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


class PageHandler:
    def __init__(
        self,
        application: FrontikApplication,
        query_params: QueryParams,
        cookie_params: dict[str, str],
        header_params: Headers,
        body_bytes: bytes,
        request_start_time: float,
        path: str,
        path_params: dict,
        remote_ip: str,
        method: str,
    ) -> None:  # request: Request
        self.application = application
        self.query_params = query_params
        self.cookie_params = cookie_params or {}
        self.header_params: Headers = header_params
        self.body_bytes = body_bytes
        self.request_start_time = request_start_time
        self.path = path
        self.path_params = path_params
        self.remote_ip = remote_ip
        self.method = method

        self._json_body = None
        self.body_arguments: dict[str, Any] = {}
        self.files: dict = {}
        self.parse_body_bytes()

        self.request_id: str = request_context.get_request_id()  # type: ignore
        self.config = application.config
        self.log = handler_logger
        self.text: Any = None

        self._finished = False

        self.statsd_client: StatsDClient | StatsDClientStub

        for integration in application.available_integrations:
            integration.initialize_handler(self)

        self.stages_logger = StagesLogger(request_start_time, self.statsd_client)

        self._debug_access: Optional[bool] = None
        self._render_postprocessors: list = []
        self._postprocessors: list = []

        self._validation_model: type[BaseValidationModel | BaseModel] = BaseValidationModel

        self.timeout_checker = None
        self.use_adaptive_strategy = False
        outer_timeout = header_params.get(OUTER_TIMEOUT_MS_HEADER)
        if outer_timeout:
            self.timeout_checker = get_timeout_checker(
                header_params.get(USER_AGENT_HEADER),
                float(outer_timeout),
                request_start_time,
            )

        self._status = 200
        self._reason: Optional[str] = None

    def __repr__(self):
        return f'{self.__module__}.{self.__class__.__name__}'

    def prepare(self) -> None:
        self.resp_headers = get_default_headers()
        self.resp_cookies: dict[str, dict] = {}

        self.finish_group = AsyncGroup(name='finish')

        self.active_limit = frontik.handler_active_limit.ActiveHandlersLimit(self.statsd_client)

        self.debug_mode = DebugMode(self)

        self.json_producer = self.application.json.get_producer(self)
        self.json = self.json_producer.json

        self.xml_producer = self.application.xml.get_producer(self)
        self.doc = self.xml_producer.doc

        self._http_client: HttpClient = self.application.http_client_factory.get_http_client(
            self.modify_http_client_request,
            self.debug_mode.enabled,
            self.use_adaptive_strategy,
        )

    # Simple getters and setters

    def get_request_headers(self) -> Headers:
        return self.header_params

    def get_path_argument(self, name, default=_ARG_DEFAULT):
        value = self.path_params.get(name, None)
        if value is None:
            if default is _ARG_DEFAULT:
                raise DefaultValueError(name)
            return default
        value = _remove_control_chars_regex.sub(' ', value)
        return value

    def get_query_argument(
        self,
        name: str,
        default: Union[str, _T] = _ARG_DEFAULT,  # type: ignore
        strip: bool = True,
    ) -> Union[str, _T]:
        args = self._get_arguments(name, strip=strip)
        if not args:
            if default is _ARG_DEFAULT:
                raise DefaultValueError(name)
            return default
        return args[-1]

    def get_query_arguments(self, name: Optional[str] = None, strip: bool = True) -> Union[list[str], dict[str, str]]:
        if name is None:
            return self._get_all_query_arguments(strip)
        return self._get_arguments(name, strip)

    def _get_all_query_arguments(self, strip: bool = True) -> dict[str, str]:
        qargs_list = self.query_params.multi_items()
        values = {}
        for qarg_k, qarg_v in qargs_list:
            v = _remove_control_chars_regex.sub(' ', qarg_v)
            if strip:
                v = v.strip()
            values[qarg_k] = v

        return values

    def _get_arguments(self, name: str, strip: bool = True) -> list[str]:
        qargs_list = self.query_params.multi_items()
        values = []
        for qarg_k, qarg_v in qargs_list:
            if qarg_k != name:
                continue

            # Get rid of any weird control chars (unless decoding gave
            # us bytes, in which case leave it alone)
            v = _remove_control_chars_regex.sub(' ', qarg_v)
            if strip:
                v = v.strip()
            values.append(v)

        return values

    def get_str_argument(
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        path_safe: bool = True,
        **kwargs: Any,
    ) -> Optional[Union[str, list[str]]]:
        if path_safe:
            return self.get_validated_argument(name, Validators.PATH_SAFE_STRING, default=default, **kwargs)
        return self.get_validated_argument(name, Validators.STRING, default=default, **kwargs)

    def get_int_argument(
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        **kwargs: Any,
    ) -> Optional[Union[int, list[int]]]:
        return self.get_validated_argument(name, Validators.INTEGER, default=default, **kwargs)

    def get_bool_argument(
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        **kwargs: Any,
    ) -> Optional[Union[bool, list[bool]]]:
        return self.get_validated_argument(name, Validators.BOOLEAN, default=default, **kwargs)

    def get_float_argument(
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        **kwargs: Any,
    ) -> Optional[Union[float, list[float]]]:
        return self.get_validated_argument(name, Validators.FLOAT, default=default, **kwargs)

    def set_validation_model(self, model: type[Union[BaseValidationModel, BaseModel]]) -> None:
        if issubclass(model, BaseModel):
            self._validation_model = model
        else:
            raise TypeError('model is not subclass of BaseClass')

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
                validated_default = self._validation_model(**params).model_dump().get(validator)
            except ValidationError:
                raise DefaultValueError(name)
        else:
            validated_default = default

        value: Any
        if array and from_body:
            value = self.get_body_arguments(name, strip)
        elif from_body:
            value = self.get_body_argument(name, validated_default, strip)
        elif array:
            value = self.get_query_arguments(name, strip)
        else:
            value = self.get_query_argument(name, validated_default, strip)

        try:
            params = {validator: value}
            validated_value = self._validation_model(**params).model_dump().get(validator)
        except ValidationError:
            if default is _ARG_DEFAULT:
                raise TypedArgumentError(http.client.BAD_REQUEST, f'"{name}" argument is invalid')
            return default

        return validated_value

    def get_body_arguments(
        self, name: Optional[str] = None, strip: bool = True
    ) -> Union[list[str], dict[str, list[str]]]:
        if name is None:
            return self._get_all_body_arguments(strip)
        return self._get_body_arguments(name, strip)

    def _get_all_body_arguments(self, strip: bool) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for key, values in self.body_arguments.items():
            result[key] = []
            for v in values:
                s = self.decode_argument(v)
                if isinstance(s, str):
                    s = _remove_control_chars_regex.sub(' ', s)
                if strip:
                    s = s.strip()
                result[key].append(s)
        return result

    def get_body_argument(self, name: str, default: Any = _ARG_DEFAULT, strip: bool = True) -> Optional[str]:
        if self._get_request_mime_type() == media_types.APPLICATION_JSON:
            if name not in self.json_body and default is _ARG_DEFAULT:
                raise DefaultValueError(name)

            result = self.json_body.get(name, default)

            if strip and isinstance(result, str):
                return result.strip()

            return result

        if default is _ARG_DEFAULT:
            return self._get_body_argument(name, strip=strip)
        return self._get_body_argument(name, default, strip)

    def _get_body_argument(
        self,
        name: str,
        default: Any = _ARG_DEFAULT,
        strip: bool = True,
    ) -> Optional[str]:
        args = self._get_body_arguments(name, strip=strip)
        if not args:
            if default is _ARG_DEFAULT:
                raise DefaultValueError(name)
            return default
        return args[-1]

    def _get_body_arguments(self, name: str, strip: bool = True) -> list[str]:
        values = []
        for v in self.body_arguments.get(name, []):
            s = self.decode_argument(v, name=name)
            if isinstance(s, str):
                s = _remove_control_chars_regex.sub(' ', s)
            if strip:
                s = s.strip()
            values.append(s)
        return values

    def parse_body_bytes(self) -> None:
        if self._get_request_mime_type() == media_types.APPLICATION_JSON:
            return
        else:
            parse_body_arguments(
                self.get_header('Content-Type', ''),
                self.body_bytes,
                self.body_arguments,
                self.files,
                self.header_params,  # type: ignore
            )

    @property
    def json_body(self):
        if self._json_body is None:
            self._json_body = self._get_json_body()
        return self._json_body

    def _get_json_body(self) -> Any:
        try:
            return json_decode(self.body_bytes)
        except FrontikJsonDecodeError as _:
            raise JSONBodyParseError()

    def decode_argument(self, value: bytes, name: Optional[str] = None) -> str:
        try:
            return value.decode('utf-8')
        except UnicodeError:
            self.log.warning('cannot decode utf-8 body parameter %s, trying other charsets', name)

        try:
            return frontik.util.decode_string_from_charset(value)
        except UnicodeError:
            self.log.exception('cannot decode body parameter %s, ignoring invalid chars', name)
            return value.decode('utf-8', 'ignore')

    @overload
    def get_header(self, param_name: str, default: None = None) -> Optional[str]: ...

    @overload
    def get_header(self, param_name: str, default: str) -> str: ...

    def get_header(self, param_name: str, default: Optional[str] = None) -> Optional[str]:
        return self.header_params.get(param_name.lower(), default)

    def set_header(self, k: str, v: str) -> None:
        self.resp_headers[k] = v

    def _get_request_mime_type(self) -> str:
        content_type = self.get_header('Content-Type', '')
        return re.split(MEDIA_TYPE_PARAMETERS_SEPARATOR_RE, content_type)[0]

    def clear_header(self, name: str) -> None:
        if name in self.resp_headers:
            del self.resp_headers[name]

    def clear_cookie(self, name: str, path: str = '/', domain: Optional[str] = None) -> None:
        expires = datetime.datetime.now() - datetime.timedelta(days=365)
        self.set_cookie(name, value='', expires=expires, path=path, domain=domain)

    def get_cookie(self, param_name: str, default: Optional[str]) -> Optional[str]:
        return self.cookie_params.get(param_name, default)

    def set_cookie(
        self,
        name: str,
        value: Union[str, bytes],
        domain: Optional[str] = None,
        expires: Optional[Union[float, tuple, datetime.datetime]] = None,
        path: str = '/',
        expires_days: Optional[float] = None,
        # Keyword-only args start here for historical reasons.
        *,
        max_age: Optional[int] = None,
        httponly: bool = False,
        secure: bool = False,
        samesite: Optional[str] = None,
    ) -> None:
        name = str(name)
        value = str(value)
        if re.search(r'[\x00-\x20]', name + value):
            # Don't let us accidentally inject bad stuff
            raise ValueError('Invalid cookie %s: %s', name, value)

        if name in self.resp_cookies:
            del self.resp_cookies[name]
        self.resp_cookies[name] = {'value': value}
        morsel = self.resp_cookies[name]
        if domain:
            morsel['domain'] = domain
        if expires_days is not None and not expires:
            expires = datetime.datetime.now() + datetime.timedelta(days=expires_days)
        if expires:
            morsel['expires'] = format_timestamp(expires)
        if path:
            morsel['path'] = path
        if max_age:
            # Note change from _ to -.
            morsel['max_age'] = str(max_age)
        if httponly:
            # Note that SimpleCookie ignores the value here. The presense of an
            # httponly (or secure) key is treated as true.
            morsel['httponly'] = True
        if secure:
            morsel['secure'] = True
        if samesite:
            morsel['samesite'] = samesite

    # Requests handling

    def require_debug_access(self, login: Optional[str] = None, passwd: Optional[str] = None) -> None:
        if self._debug_access is None:
            if options.debug:
                debug_access = True
            else:
                check_login = login if login is not None else options.debug_login
                check_passwd = passwd if passwd is not None else options.debug_password
                frontik.auth.check_debug_auth(self, check_login, check_passwd)
                debug_access = True

            self._debug_access = debug_access

    def set_status(self, status_code: int, reason: Optional[str] = None) -> None:
        status_code = status_code if status_code in ALLOWED_STATUSES else http.client.SERVICE_UNAVAILABLE

        self._status = status_code
        self._reason = reason

    def get_status(self) -> int:
        return self._status

    def redirect(self, url: str, permanent: bool = False, status: Optional[int] = None) -> None:
        if url.startswith('//'):
            raise RuntimeError('403 cannot redirect path with two initial slashes')
        self.log.info('redirecting to: %s', url)
        if status is None:
            status = 301 if permanent else 302
        else:
            assert isinstance(status, int)
            assert 300 <= status <= 399
        raise RedirectPageSignal(url, status)

    def finish(self, data: Optional[Union[str, bytes, dict]] = None) -> None:
        raise FinishPageSignal(data)

    async def get_page_fail_fast(self, request_result: RequestResult) -> tuple[int, dict, Any]:
        return await self.__return_error(request_result.status_code, error_info={'is_fail_fast': True})

    async def post_page_fail_fast(self, request_result: RequestResult) -> tuple[int, dict, Any]:
        return await self.__return_error(request_result.status_code, error_info={'is_fail_fast': True})

    async def put_page_fail_fast(self, request_result: RequestResult) -> tuple[int, dict, Any]:
        return await self.__return_error(request_result.status_code, error_info={'is_fail_fast': True})

    async def delete_page_fail_fast(self, request_result: RequestResult) -> tuple[int, dict, Any]:
        return await self.__return_error(request_result.status_code, error_info={'is_fail_fast': True})

    async def __return_error(self, response_code: int, **kwargs: Any) -> tuple[int, dict, Any]:
        return await self.send_error(response_code if 300 <= response_code < 500 else 502, **kwargs)

    # Finish page

    def is_finished(self) -> bool:
        return self._finished

    async def finish_with_postprocessors(self) -> tuple[int, dict, Any]:
        if self.finish_group.pending():
            self.log.error('finish_with_postprocessors before finish group done')
            self.finish_group.abort()

        content = await self._postprocess()
        return self.get_status(), self.resp_headers, content

    def run_task(self: PageHandler, coro: Coroutine) -> Task:
        task = asyncio.create_task(coro)
        self.finish_group.add_future(task)
        return task

    async def _postprocess(self) -> Any:
        if self._finished:
            self.log.info('page was already finished, skipping postprocessors')
            return

        self.stages_logger.commit_stage('page')
        postprocessors_completed = await self._run_postprocessors(self._postprocessors)

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

    def on_finish(self, status: int) -> None:
        self.stages_logger.commit_stage('flush')
        self.stages_logger.flush_stages(status)

    async def handle_request_exception(self, ex: BaseException) -> tuple[int, dict, Any]:
        if isinstance(ex, FinishPageSignal):
            chunk = _data_to_chunk(ex.data, self.resp_headers)
            return self.get_status(), self.resp_headers, chunk

        if isinstance(ex, RedirectPageSignal):
            self.set_header('Location', ex.url)
            return ex.status, self.resp_headers, None

        if isinstance(ex, FinishWithPostprocessors):
            if ex.wait_finish_group:
                await self.finish_group.finish()
            return await self.finish_with_postprocessors()

        if isinstance(ex, HTTPErrorWithPostprocessors):
            self.set_status(ex.status_code)
            return await self.finish_with_postprocessors()

        if isinstance(ex, HTTPException):
            self.resp_cookies = {}
            if ex.headers is None:
                ex.headers = {'Content-Type': media_types.TEXT_PLAIN}

            self.log.error('HTTPException with code: %s, reason: %s', ex.status_code, ex.detail)

            if hasattr(self, 'write_error'):
                return await self.write_error(ex.status_code, exc_info=sys.exc_info())

            return build_error_data(ex.status_code, ex.detail)

        if isinstance(ex, FailFastError):
            request = ex.failed_result.request

            if self.log.isEnabledFor(logging.WARNING):
                _max_uri_length = 24

                request_name = request.host + request.path[:_max_uri_length]
                if len(request.path) > _max_uri_length:
                    request_name += '...'
                if request.name:
                    request_name = f'{request_name} ({request.name})'

                self.log.error(
                    'FailFastError: request %s failed with %s code',
                    request_name,
                    ex.failed_result.status_code,
                )

            error_method_name = f'{self.method.lower()}_page_fail_fast'
            method = getattr(self, error_method_name, None)
            if callable(method):
                return await method(ex.failed_result)
            else:
                return await self.__return_error(ex.failed_result.status_code, error_info={'is_fail_fast': True})

        else:
            raise ex

    async def send_error(self, status_code: int = 500, **kwargs: Any) -> tuple[int, dict, Any]:
        self.stages_logger.commit_stage('page')

        self._reason = kwargs.get('reason')

        self.set_status(status_code, reason=self._reason)
        return build_error_data(status_code, self._reason)

    def cleanup(self) -> None:
        self._finished = True
        if hasattr(self, 'active_limit'):
            self.active_limit.release()

    # postprocessors

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

        if self.resp_headers.get('Content-Type') is None:
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
                authorization = self.get_header(header_name)
                if authorization is not None:
                    balanced_request.headers[header_name] = authorization

    def get_url(
        self,
        host: str,
        path: str,
        *,
        name: Optional[str] = None,
        data: Any = None,
        headers: Any = None,
        follow_redirects: bool = True,
        profile: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        request_timeout: Optional[float] = None,
        max_timeout_tries: Optional[int] = None,
        speculative_timeout_pct: Optional[float] = None,
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
        name: Optional[str] = None,
        data: Any = None,
        headers: Any = None,
        follow_redirects: bool = True,
        profile: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        request_timeout: Optional[float] = None,
        max_timeout_tries: Optional[int] = None,
        speculative_timeout_pct: Optional[float] = None,
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
        name: Optional[str] = None,
        data: Any = '',
        headers: Any = None,
        files: Any = None,
        content_type: Optional[str] = None,
        follow_redirects: bool = True,
        profile: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        request_timeout: Optional[float] = None,
        max_timeout_tries: Optional[int] = None,
        idempotent: bool = False,
        speculative_timeout_pct: Optional[float] = None,
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
        name: Optional[str] = None,
        data: Any = '',
        headers: Any = None,
        content_type: Optional[str] = None,
        follow_redirects: bool = True,
        profile: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        request_timeout: Optional[float] = None,
        max_timeout_tries: Optional[int] = None,
        idempotent: bool = True,
        speculative_timeout_pct: Optional[float] = None,
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
        name: Optional[str] = None,
        data: Any = None,
        headers: Any = None,
        content_type: Optional[str] = None,
        profile: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        request_timeout: Optional[float] = None,
        max_timeout_tries: Optional[int] = None,
        speculative_timeout_pct: Optional[float] = None,
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
        if waited and (self.is_finished() or self.finish_group.done()):
            handler_logger.info(
                'attempted to make waited http request to %s %s in finished handler, ignoring',
                host,
                path,
            )

            future: Future = Future()
            future.set_exception(AbortAsyncGroup('attempted to make waited http request is finished handler'))
            return future

        future = client_method()

        if waited:
            self.finish_group.add_future(future)

        return future

    def log_request(self, request: Request) -> None:
        request_time = int(1000.0 * (time.time() - self.request_start_time))
        extra = {
            'ip': request.client.host if request.client else None,
            'rid': request_context.get_request_id(),
            'status': self.get_status(),
            'time': request_time,
            'method': request.method,
            'uri': request.url.path,
        }

        handler_name = request_context.get_handler_name()
        if handler_name:
            extra['controller'] = handler_name

        JSON_REQUESTS_LOGGER.info('', extra={CUSTOM_JSON_EXTRA: extra})


PageHandlerT = TypeVar('PageHandlerT', bound=PageHandler)


def get_current_handler(_: Union[PageHandlerT, Type[PageHandler]] = PageHandler) -> PageHandlerT:
    async def handler_getter(request: Request) -> PageHandlerT:
        return request.state.handler

    return Depends(handler_getter)


def get_default_headers() -> dict[str, str]:
    request_id = request_context.get_request_id() or ''
    return {
        'Server': f'Frontik/{frontik_version}',
        'X-Request-Id': request_id,
    }


def build_error_data(status_code: int = 500, message: Optional[str] = 'Internal Server Error') -> tuple[int, dict, Any]:
    headers = get_default_headers()
    headers['Content-Type'] = media_types.TEXT_HTML
    content = f'<html><title>{status_code}: {message}</title><body>{status_code}: {message}</body></html>'
    return status_code, headers, content


def _data_to_chunk(data: Any, headers: dict) -> bytes:
    result: bytes = b''
    if data is None:
        return result
    if isinstance(data, str):
        result = data.encode('utf-8')
    elif isinstance(data, dict):
        chunk = json.dumps(data).replace('</', '<\\/')
        result = chunk.encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=UTF-8'
    elif isinstance(data, bytes):
        result = data
    else:
        raise TypeError(f'unexpected type of chunk - {type(data)}')
    return result


async def process_request(request: Request, call_next: Callable, route: APIRoute) -> Response:
    handler: PageHandler = request.state.handler

    try:
        request_context.set_handler_name(f'{route.endpoint.__module__}.{route.endpoint.__name__}')

        handler.prepare()
        handler.stages_logger.commit_stage('prepare')
        _response = await call_next(request)

        await handler.finish_group.finish()
        handler.stages_logger.commit_stage('page')

        content = await handler._postprocess()
        headers = handler.resp_headers
        status = handler.get_status()

        handler.stages_logger.commit_stage('postprocess')

    except Exception as ex:
        try:
            status, headers, content = await handler.handle_request_exception(ex)
        except Exception as exc:
            handler_logger.error('request processing has failed: %s', exc)
            if getattr(handler, '_debug_enabled', False):
                status, headers, content = build_error_data()
            elif hasattr(handler, 'write_error'):
                status, headers, content = await handler.write_error(exc_info=sys.exc_info())
            else:
                raise

    finally:
        handler.cleanup()

    if status in (204, 304) or (100 <= status < 200):
        for h in ('Content-Encoding', 'Content-Language', 'Content-Type'):
            if h in headers:
                headers.pop(h)
        content = None

    if getattr(handler, '_debug_enabled', False):
        chunk = _data_to_chunk(content, headers)
        debug_transform = DebugTransform(request.app.frontik_app, request)
        status, headers, content = debug_transform.transform_chunk(status, headers, chunk)

    response = Response(status_code=status, headers=headers, content=content)

    for key, values in handler.resp_cookies.items():
        response.set_cookie(key, **values)

    handler.finish_group.abort()
    handler.log_request(request)
    handler.on_finish(status)

    return response

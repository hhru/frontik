from __future__ import annotations

import base64
import contextlib
import copy
import inspect
import json
import logging
import os
import pprint
import re
import time
import traceback
from binascii import crc32
from datetime import datetime
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from lxml import etree
from lxml.builder import E
from tornado.escape import to_unicode, utf8
from tornado.httputil import HTTPHeaders

from frontik import media_types
from frontik.auth import check_debug_auth
from frontik.frontik_response import FrontikResponse
from frontik.loggers import BufferedHandler
from frontik.options import options
from frontik.request_integrations import request_context
from frontik.util import any_to_unicode, decode_string_from_charset, get_cookie_or_param_from_request
from frontik.util.xml import dict_to_xml

if TYPE_CHECKING:
    from typing import Any, Optional

    from http_client.request_response import RequestBuilder, RequestResult

    from frontik.app import FrontikApplication
    from frontik.tornado_request import FrontikTornadoServerRequest

debug_log = logging.getLogger('frontik.debug')


def response_to_xml(result: RequestResult) -> etree.Element:
    time_info = etree.Element('time_info')
    content_type = result.headers.get('Content-Type', '')
    mode = ''

    charset = content_type.partition('=')[-1] if 'charset' in content_type else 'utf-8'

    try_charsets = (charset, 'cp1251')

    raw_body = result.raw_body
    try:
        if not raw_body:
            body = ''
        elif 'text/html' in content_type:
            mode = 'html'
            body = decode_string_from_charset(raw_body, try_charsets)
        elif 'protobuf' in content_type:
            body = raw_body
        elif 'xml' in content_type:
            mode = 'xml'
            body = _pretty_print_xml(etree.fromstring(raw_body))
        elif 'json' in content_type:
            mode = 'javascript'
            body = _pretty_print_json(json.loads(raw_body))
        else:
            if 'javascript' in content_type:
                mode = 'javascript'
            body = decode_string_from_charset(raw_body, try_charsets)

    except Exception:
        debug_log.exception('cannot parse response body')
        body = raw_body

    try:
        escaped_body = re.sub(r'\\n', '\n', repr(body)[1:-1])
        response = E.response(
            E.body(escaped_body, content_type=content_type, mode=mode),
            E.code(str(result.status_code)),
            E.error(str(result.error)),
            E.size(str(len(raw_body)) if raw_body is not None else '0'),
            E.request_time(_format_number(result.elapsed_time * 1000)),
            _headers_to_xml(result.headers),
            _cookies_to_xml(result.headers),
            time_info,
        )
    except Exception:
        debug_log.exception('cannot log response info')
        response = E.response(E.body('Cannot log response info'))

    return response


def request_to_xml(request: RequestBuilder) -> etree.Element:
    content_type = request.headers.get('Content-Type', '')
    body = etree.Element('body', content_type=content_type)

    if request.body:
        try:
            if 'json' in content_type:
                body.text = _pretty_print_json(json.loads(request.body))
            elif 'protobuf' in content_type:
                body.text = repr(request.body)
            else:
                body_query = parse_qs(str(request.body), True)
                for name, values in body_query.items():
                    for value in values:
                        body.append(E.param(to_unicode(value), name=to_unicode(name)))
        except Exception:
            debug_log.exception('cannot parse request body')
            body.text = repr(request.body)

    try:
        request = E.request(
            body,
            E.start_time(_format_number(request.start_time or 0)),
            E.method(request.method),
            E.url(request.url),
            _params_to_xml(request.url),
            _headers_to_xml(request.headers),
            _cookies_to_xml(request.headers),
            E.curl(request_to_curl_string(request)),
        )
    except Exception:
        debug_log.exception('cannot parse request body')
        body.text = repr(request.body)
        request = E.request(body)

    return request


def balanced_request_to_xml(balanced_request: RequestBuilder, retry: int, datacenter: str) -> etree.Element:
    info = etree.Element('meta-info')

    if balanced_request.upstream_name != balanced_request.host:
        etree.SubElement(info, 'upstream', name=balanced_request.upstream_name.upper())
        server_params = {'datacenter': datacenter}
        etree.SubElement(info, 'server', **{key: value for key, value in server_params.items() if value})

    if retry > 0:
        etree.SubElement(info, 'retry', count=str(retry))

    return info


def request_to_curl_string(request: RequestBuilder) -> str:
    def _escape_apos(string: str) -> str:
        return string.replace("'", "'\"'\"'")

    try:
        request_body = _escape_apos(request.body.decode('ascii')) if request.body else None
        is_binary_body = False
    except UnicodeError:
        request_body = repr(request.body).strip('b')
        is_binary_body = True

    curl_headers = HTTPHeaders(request.headers)
    if request.body and 'Content-Length' not in curl_headers:
        curl_headers['Content-Length'] = str(len(request.body))

    if is_binary_body:
        curl_echo_data = f'echo -e {request_body} |'
        curl_data_string = '--data-binary @-'
    else:
        curl_echo_data = ''
        curl_data_string = f"--data '{request_body}'" if request_body else ''

    def _format_header(key: str) -> str:
        header_value = any_to_unicode(curl_headers[key])
        return f"-H '{key}: {_escape_apos(header_value)}'"

    return "{echo} curl -X {method} '{url}' {headers} {data}".format(
        echo=curl_echo_data,
        method=request.method,
        url=to_unicode(request.url),
        headers=' '.join(_format_header(k) for k in sorted(curl_headers.keys())),
        data=curl_data_string,
    ).strip()


def _get_query_parameters(url: str) -> dict:
    url = 'http://' + url if not re.match(r'[a-z]+://.+\??.*', url, re.IGNORECASE) else url
    return parse_qs(urlparse(url).query, True)


def _params_to_xml(url: str) -> etree.Element:
    params = etree.Element('params')
    query = _get_query_parameters(url)
    for name, values in query.items():
        for value in values:
            try:
                params.append(E.param(to_unicode(value), name=to_unicode(name)))
            except ValueError:  # noqa: PERF203
                debug_log.exception('bad parameter name or value')
                params.append(E.param(repr(value), name=repr(name)))
    return params


def _headers_to_xml(request_or_response_headers: HTTPHeaders) -> etree.Element:
    headers = etree.Element('headers')
    for name, value in request_or_response_headers.items():
        if name != 'Cookie':
            str_value = value if isinstance(value, str) else str(value)
            headers.append(E.header(to_unicode(str_value), name=name))
    return headers


def _cookies_to_xml(request_or_response_headers: HTTPHeaders) -> etree.Element:
    cookies = etree.Element('cookies')
    if 'Cookie' in request_or_response_headers:
        _cookies: SimpleCookie = SimpleCookie(request_or_response_headers['Cookie'])
        for cookie in _cookies:
            cookies.append(E.cookie(_cookies[cookie].value, name=cookie))
    return cookies


def _exception_to_xml(exc_info: tuple, log: logging.Logger = debug_log) -> etree.Element:
    exc_node = etree.Element('exception')

    try:
        trace_node = etree.Element('trace')
        trace = exc_info[2]
        while trace:
            frame = trace.tb_frame
            trace_step_node = etree.Element('step')
            trace_lines = etree.Element('lines')

            try:
                lines, starting_line = inspect.getsourcelines(frame)
            except OSError:
                lines, starting_line = [], 0

            for i, line in enumerate(lines):
                line_node = etree.Element('line')
                line_node.append(E.text(to_unicode(line)))
                line_node.append(E.number(str(starting_line + i)))
                if starting_line + i == frame.f_lineno:
                    line_node.set('selected', 'true')
                trace_lines.append(line_node)

            trace_step_node.append(trace_lines)
            trace_step_node.append(E.file(to_unicode(inspect.getfile(frame))))
            trace_step_node.append(E.locals(pprint.pformat(frame.f_locals)))
            trace_node.append(trace_step_node)
            trace = trace.tb_next
        exc_node.append(trace_node)
    except Exception:
        log.exception('cannot add traceback lines')

    exc_node.append(E.text(''.join(map(to_unicode, traceback.format_exception(*exc_info)))))
    return exc_node


_format_number = '{:.4f}'.format


def _pretty_print_xml(node: etree.Element) -> str:
    return etree.tostring(node, pretty_print=True, encoding='unicode')


def _pretty_print_json(node: Any) -> str:
    return json.dumps(node, sort_keys=True, indent=2, ensure_ascii=False)


def _string_to_color(value: None | str | bytes) -> tuple[str, str]:
    value_hash = crc32(utf8(value)) % 0xFFFFFFFF  # type: ignore
    r = (value_hash & 0xFF0000) >> 16
    g = (value_hash & 0x00FF00) >> 8
    b = value_hash & 0x0000FF
    bgcolor = f'#{r:02x}{g:02x}{b:02x}'
    fgcolor = 'black' if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0xFF / 2 else 'white'
    return bgcolor, fgcolor


class DebugBufferedHandler(BufferedHandler):
    FIELDS = (
        'created',
        'filename',
        'funcName',
        'levelname',
        'levelno',
        'lineno',
        'module',
        'msecs',
        'name',
        'pathname',
        'process',
        'processName',
        'relativeCreated',
        'threadName',
    )

    def produce_all(self):
        log_data = etree.Element('log')

        for record in self.records:
            log_data.append(self._produce_one(record))

        return copy.deepcopy(log_data)

    def _produce_one(self, record: logging.LogRecord) -> etree.Element:
        entry_attrs = {}
        for field in self.FIELDS:
            val = getattr(record, field)
            if val is not None:
                entry_attrs[field] = to_unicode(str(val))

        entry_attrs['msg'] = to_unicode(record.getMessage())

        try:
            entry = etree.Element('entry', **entry_attrs)
        except ValueError:
            debug_log.exception('error creating log entry with attrs: %s', entry_attrs)
            entry = etree.Element('entry')

        entry.set('asctime', str(datetime.fromtimestamp(record.created)))

        if record.exc_info:
            entry.append(_exception_to_xml(record.exc_info))

        if hasattr(record, '_response') and getattr(record, '_response', None) is not None:
            entry.append(response_to_xml(record._response))

        if hasattr(record, '_request') and getattr(record, '_request', None) is not None:
            entry.append(request_to_xml(record._request))
            entry.append(
                balanced_request_to_xml(record._request, record._request_retry, record._datacenter),  # type: ignore
            )

        if hasattr(record, '_debug_response') and getattr(record, '_debug_response', None) is not None:
            entry.append(E.debug(record._debug_response))

        if hasattr(record, '_xslt_profile') and getattr(record, '_xslt_profile', None) is not None:
            entry.append(record._xslt_profile)

        if hasattr(record, '_xml') and getattr(record, '_xml', None) is not None:
            entry.append(E.text(etree.tostring(record._xml, encoding='unicode')))

        if hasattr(record, '_protobuf') and getattr(record, '_protobuf', None) is not None:
            entry.append(E.text(str(record._protobuf)))

        if hasattr(record, '_text') and getattr(record, '_text', None) is not None:
            entry.append(E.text(to_unicode(record._text)))

        if hasattr(record, '_stage') and getattr(record, '_stage', None) is not None:
            entry.append(
                E.stage(
                    E.name(record._stage.name),
                    E.delta(_format_number(record._stage.delta)),
                    E.start_delta(_format_number(record._stage.start_delta)),
                ),
            )

        return entry


DEBUG_HEADER_NAME = 'X-Hh-Debug'
DEBUG_XSL = os.path.join(os.path.dirname(__file__), 'debug/debug.xsl')


def _data_to_chunk(data: Any) -> bytes:
    result: bytes = b''
    if data is None:
        return result
    if isinstance(data, str):
        result = data.encode('utf-8')
    elif isinstance(data, dict):
        chunk = json.dumps(data).replace('</', '<\\/')
        result = chunk.encode('utf-8')
    elif isinstance(data, bytes):
        result = data
    else:
        raise TypeError(f'unexpected type of chunk - {type(data)}')
    return result


class DebugTransform:
    def __init__(self, application: FrontikApplication, debug_mode: DebugMode) -> None:
        self.application = application
        self.debug_mode = debug_mode

    def is_enabled(self) -> bool:
        return self.debug_mode.enabled

    def is_inherited(self) -> bool:
        return self.debug_mode.inherited

    def transform_chunk(
        self, tornado_request: FrontikTornadoServerRequest, response: FrontikResponse
    ) -> FrontikResponse:
        if not self.is_enabled():
            return response

        cors_headers = {
            header: response.headers[header]
            for header in (
                'access-control-allow-credentials',
                'access-control-allow-origin',
            )
            if header in response.headers
        }

        if not self.is_inherited():
            wrap_headers = {'Content-Type': media_types.TEXT_HTML, **cors_headers}
        else:
            wrap_headers = {
                'Content-Type': media_types.APPLICATION_XML,
                DEBUG_HEADER_NAME: 'true',
                **cors_headers,
            }

        chunk = b'Streamable response' if response.headers_written else _data_to_chunk(response.body)
        start_time = time.time()
        handler_name = request_context.get_handler_name()

        debug_log_data = request_context.get_debug_log_handler().produce_all()  # type: ignore
        debug_log_data.set('code', str(int(response.status_code)))
        debug_log_data.set('handler-name', handler_name or 'unknown handler')
        debug_log_data.set('started', _format_number(tornado_request._start_time))
        debug_log_data.set('request-id', str(tornado_request.request_id))
        debug_log_data.set('stages-total', _format_number((time.time() - tornado_request._start_time) * 1000))

        try:
            debug_log_data.append(E.versions(_pretty_print_xml(self.application.get_frontik_and_apps_versions())))
        except Exception:
            debug_log.exception('cannot add version information')
            debug_log_data.append(E.versions('failed to get version information'))

        try:
            debug_log_data.append(E.status(_pretty_print_json(self.application.get_current_status())))
        except Exception:
            debug_log.exception('cannot add status information')
            debug_log_data.append(E.status('failed to get status information'))

        debug_log_data.append(
            E.request(
                E.method(tornado_request.method),
                _params_to_xml(str(tornado_request.uri)),
                _headers_to_xml(tornado_request.headers),
                _cookies_to_xml(tornado_request.headers),
            ),
        )

        debug_log_data.append(E.response(_headers_to_xml(response.headers), _cookies_to_xml(response.headers)))

        original_response = {
            'buffer': base64.b64encode(chunk),
            'headers': dict(response.headers),
            'code': int(response.status_code),
        }

        debug_log_data.append(dict_to_xml(original_response, 'original-response'))
        debug_log_data.set('response-size', str(len(chunk)))
        debug_log_data.set('generate-time', _format_number((time.time() - start_time) * 1000))

        for upstream in debug_log_data.xpath('//meta-info/upstream'):
            bgcolor, fgcolor = _string_to_color(upstream.get('name'))
            upstream.set('bgcolor', bgcolor)
            upstream.set('fgcolor', fgcolor)

        if not self.debug_mode.inherited:
            try:
                transform = etree.XSLT(etree.parse(DEBUG_XSL))
                log_document = utf8(str(transform(debug_log_data)))
            except Exception:
                debug_log.exception('XSLT debug file error')

                with contextlib.suppress(Exception):
                    debug_log.error(
                        'XSL error log entries:\n'
                        + '\n'.join(f'{m.filename}:{m.line}:{m.column}\n\t{m.message}' for m in transform.error_log),
                    )

                log_document = etree.tostring(debug_log_data, encoding='UTF-8', xml_declaration=True)
        else:
            log_document = etree.tostring(debug_log_data, encoding='UTF-8', xml_declaration=True)

        return FrontikResponse(status_code=200, headers=wrap_headers, body=log_document)


class DebugMode:
    def __init__(self, tornado_request: FrontikTornadoServerRequest) -> None:
        self.debug_value = get_cookie_or_param_from_request(tornado_request, 'debug')
        self.notpl = get_cookie_or_param_from_request(tornado_request, 'notpl')
        self.notrl = get_cookie_or_param_from_request(tornado_request, 'notrl')
        self.noxsl = get_cookie_or_param_from_request(tornado_request, 'noxsl')
        self.mode_values = self.debug_value.split(',') if self.debug_value is not None else ''
        self.inherited = tornado_request.headers.get(DEBUG_HEADER_NAME, None)
        self.pass_debug = False
        self.enabled = False
        self.debug_response = False
        self.profile_xslt = False
        self.failed_auth_headers: Optional[dict] = None
        self.need_auth = (
            self.debug_value is not None
            or self.inherited
            or self.notpl is not None
            or self.notrl is not None
            or self.noxsl is not None
        )
        self.auth_failed: Optional[bool] = None

        if self.inherited:
            debug_log.debug('debug mode is inherited due to %s request header', DEBUG_HEADER_NAME)

    def require_debug_access(self, headers: HTTPHeaders, auth_failed: Optional[bool] = None) -> None:
        if auth_failed is True:
            self.auth_failed = True
            return

        if options.debug or auth_failed is False:
            self.auth_failed = False
            self.on_auth_ok()
            return

        self.failed_auth_headers = check_debug_auth(headers, options.debug_login, options.debug_password)
        if self.failed_auth_headers is None:
            self.auth_failed = False
            self.on_auth_ok()
            return

        self.auth_failed = True

    def on_auth_ok(self) -> None:
        self.debug_response = self.debug_value is not None or self.inherited
        self.enabled = True
        self.pass_debug = 'nopass' not in self.mode_values or bool(self.inherited)
        self.profile_xslt = 'xslt' in self.mode_values

        request_context.set_debug_log_handler(DebugBufferedHandler())

        if self.pass_debug:
            debug_log.debug('%s header will be passed to all requests', DEBUG_HEADER_NAME)

import base64
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
from io import BytesIO
from urllib.parse import parse_qs, urlparse

from lxml import etree
from lxml.builder import E
from tornado.escape import to_unicode, utf8
from tornado.httpclient import HTTPResponse
from tornado.httputil import HTTPHeaders
from tornado.web import OutputTransform

import frontik.util
import frontik.xml_util
from frontik import media_types
from frontik.loggers import BufferedHandler
from frontik.request_context import RequestContext

debug_log = logging.getLogger('frontik.debug')


def response_to_xml(response):
    time_info = etree.Element('time_info')
    content_type = response.headers.get('Content-Type', '')
    mode = ''

    if 'charset' in content_type:
        charset = content_type.partition('=')[-1]
    else:
        charset = 'utf-8'

    try_charsets = (charset, 'cp1251')

    try:
        if not response.body:
            body = ''
        elif 'text/html' in content_type:
            mode = 'html'
            body = frontik.util.decode_string_from_charset(response.body, try_charsets)
        elif 'protobuf' in content_type:
            body = repr(response.body)
        elif 'xml' in content_type:
            mode = 'xml'
            body = _pretty_print_xml(etree.fromstring(response.body))
        elif 'json' in content_type:
            mode = 'javascript'
            body = _pretty_print_json(json.loads(response.body))
        else:
            if 'javascript' in content_type:
                mode = 'javascript'
            body = frontik.util.decode_string_from_charset(response.body, try_charsets)

    except Exception:
        debug_log.exception('cannot parse response body')
        body = repr(response.body)

    try:
        for name, value in response.time_info.items():
            time_info.append(E.time(f'{value * 1000} ms', name=name))
    except Exception:
        debug_log.exception('cannot append time info')

    try:
        response = E.response(
            E.body(body, content_type=content_type, mode=mode),
            E.code(str(response.code)),
            E.error(str(response.error)),
            E.size(str(len(response.body)) if response.body is not None else '0'),
            E.request_time(_format_number(response.request_time * 1000)),
            _headers_to_xml(response.headers),
            _cookies_to_xml(response.headers),
            time_info,
        )
    except Exception:
        debug_log.exception('cannot log response info')
        response = E.response(E.body('Cannot log response info'))

    return response


def request_to_xml(request):
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
            E.start_time(_format_number(request.start_time)),
            E.method(request.method),
            E.url(request.url),
            _params_to_xml(request.url),
            _headers_to_xml(request.headers),
            _cookies_to_xml(request.headers),
            E.curl(
                request_to_curl_string(request)
            )
        )
    except Exception:
        debug_log.exception('cannot parse request body')
        body.text = repr(request.body)
        request = E.request(body)

    return request


def balanced_request_to_xml(balanced_request, retry, rack, datacenter):
    info = etree.Element('meta-info')

    if balanced_request.upstream.balanced:
        etree.SubElement(info, 'upstream', name=balanced_request.upstream.name.upper())
        server_params = {'rack': rack, 'datacenter': datacenter}
        etree.SubElement(info, 'server', **{key: value for key, value in server_params.items() if value})

    if retry > 0:
        etree.SubElement(info, 'retry', count=str(retry))

    return info


def response_from_debug(request, response):
    debug_response = etree.XML(response.body)
    original_response = debug_response.find('original-response')

    if original_response is not None:
        response_info = frontik.xml_util.xml_to_dict(original_response)
        original_response.getparent().remove(original_response)

        original_buffer = base64.b64decode(response_info.get('buffer', ''))

        headers = dict(response.headers)
        response_info_headers = response_info.get('headers', {})
        if response_info_headers:
            headers.update(response_info_headers)

        fake_response = HTTPResponse(
            request,
            int(response_info.get('code', 599)),
            headers=HTTPHeaders(headers),
            buffer=BytesIO(original_buffer),
            effective_url=response.effective_url,
            request_time=response.request_time,
            time_info=response.time_info
        )

        return debug_response, fake_response

    return None


def request_to_curl_string(request):
    def _escape_apos(string):
        return string.replace("'", "'\"'\"'")

    try:
        request_body = _escape_apos(request.body.decode('ascii')) if request.body else None
        is_binary_body = False
    except UnicodeError:
        request_body = repr(request.body).strip('b')
        is_binary_body = True

    curl_headers = HTTPHeaders(request.headers)
    if request.body and 'Content-Length' not in curl_headers:
        curl_headers['Content-Length'] = len(request.body)

    if is_binary_body:
        curl_echo_data = f'echo -e {request_body} |'
        curl_data_string = '--data-binary @-'
    else:
        curl_echo_data = ''
        curl_data_string = f"--data '{request_body}'" if request_body else ''

    def _format_header(key):
        header_value = frontik.util.any_to_unicode(curl_headers[key])
        return f"-H '{key}: {_escape_apos(header_value)}'"

    return "{echo} curl -X {method} '{url}' {headers} {data}".format(
        echo=curl_echo_data,
        method=request.method,
        url=to_unicode(request.url),
        headers=' '.join(_format_header(k) for k in sorted(curl_headers.keys())),
        data=curl_data_string
    ).strip()


def _get_query_parameters(url):
    url = 'http://' + url if not re.match(r'[a-z]+://.+\??.*', url, re.IGNORECASE) else url
    return parse_qs(urlparse(url).query, True)


def _params_to_xml(url):
    params = etree.Element('params')
    query = _get_query_parameters(url)
    for name, values in query.items():
        for value in values:
            try:
                params.append(E.param(to_unicode(value), name=to_unicode(name)))
            except UnicodeDecodeError:
                debug_log.exception('cannot decode parameter name or value')
                params.append(E.param(repr(value), name=repr(name)))
    return params


def _headers_to_xml(request_or_response_headers):
    headers = etree.Element('headers')
    for name, value in request_or_response_headers.items():
        if name != 'Cookie':
            str_value = value if isinstance(value, str) else str(value)
            headers.append(E.header(to_unicode(str_value), name=name))
    return headers


def _cookies_to_xml(request_or_response_headers):
    cookies = etree.Element('cookies')
    if 'Cookie' in request_or_response_headers:
        _cookies = SimpleCookie(request_or_response_headers['Cookie'])
        for cookie in _cookies:
            cookies.append(E.cookie(_cookies[cookie].value, name=cookie))
    return cookies


def _exception_to_xml(exc_info, log=debug_log):
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
            except IOError:
                lines, starting_line = [], None

            for i, l in enumerate(lines):
                line_node = etree.Element('line')
                line_node.append(E.text(to_unicode(l)))
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


def _pretty_print_xml(node):
    return etree.tostring(node, pretty_print=True, encoding='unicode')


def _pretty_print_json(node):
    return json.dumps(node, sort_keys=True, indent=2, ensure_ascii=False)


def _string_to_color(value):
    value_hash = crc32(utf8(value)) % 0xffffffff
    return '#%02x%02x%02x' % ((value_hash & 0xFF0000) >> 16, (value_hash & 0x00FF00) >> 8, value_hash & 0x0000FF)


class DebugBufferedHandler(BufferedHandler):
    FIELDS = ('created', 'filename', 'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
              'name', 'pathname', 'process', 'processName', 'relativeCreated', 'threadName')

    def produce_all(self):
        log_data = etree.Element('log')

        for record in self.records:
            log_data.append(self._produce_one(record))

        return copy.deepcopy(log_data)

    def _produce_one(self, record):
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

        if record.exc_info is not None:
            entry.append(_exception_to_xml(record.exc_info))

        if getattr(record, '_response', None) is not None:
            entry.append(response_to_xml(record._response))

        if getattr(record, '_request', None) is not None:
            entry.append(request_to_xml(record._request))

        if getattr(record, '_balanced_request', None) is not None:
            entry.append(balanced_request_to_xml(record._balanced_request, record._request_retry,
                                                 record._rack, record._datacenter))

        if getattr(record, '_debug_response', None) is not None:
            entry.append(E.debug(record._debug_response))

        if getattr(record, '_xslt_profile', None) is not None:
            entry.append(record._xslt_profile)

        if getattr(record, '_xml', None) is not None:
            entry.append(E.text(etree.tostring(record._xml, encoding='unicode')))

        if getattr(record, '_protobuf', None) is not None:
            entry.append(E.text(str(record._protobuf)))

        if getattr(record, '_text', None) is not None:
            entry.append(E.text(to_unicode(record._text)))

        if getattr(record, '_stage', None) is not None:
            entry.append(E.stage(
                E.name(record._stage.name),
                E.delta(_format_number(record._stage.delta)),
                E.start_delta(_format_number(record._stage.start_delta))
            ))

        return entry


DEBUG_HEADER_NAME = 'X-Hh-Debug'
DEBUG_XSL = os.path.join(os.path.dirname(__file__), 'debug/debug.xsl')


class DebugTransform(OutputTransform):
    def __init__(self, application, request):
        self.application = application
        self.request = request

    def is_enabled(self):
        return getattr(self.request, '_debug_enabled', False)

    def is_inherited(self):
        return getattr(self.request, '_debug_inherited', False)

    def transform_first_chunk(self, status_code, headers, chunk, finishing):
        if not self.is_enabled():
            return status_code, headers, chunk

        self.status_code = status_code
        self.headers = headers
        self.chunks = [chunk]

        if not self.is_inherited():
            headers = HTTPHeaders({'Content-Type': media_types.TEXT_HTML})
        else:
            headers = HTTPHeaders({
                'Content-Type': media_types.APPLICATION_XML,
                DEBUG_HEADER_NAME: 'true'
            })

        return 200, headers, self.produce_debug_body(finishing)

    def transform_chunk(self, chunk, finishing):
        if not self.is_enabled():
            return chunk

        self.chunks.append(chunk)

        return self.produce_debug_body(finishing)

    def produce_debug_body(self, finishing):
        if not finishing:
            return b''

        start_time = time.time()

        debug_log_data = RequestContext.get('log_handler').produce_all()
        debug_log_data.set('code', str(int(self.status_code)))
        debug_log_data.set('handler-name', RequestContext.get('handler_name'))
        debug_log_data.set('started', _format_number(self.request._start_time))
        debug_log_data.set('request-id', str(self.request.request_id))
        debug_log_data.set('stages-total', _format_number((time.time() - self.request._start_time) * 1000))

        try:
            debug_log_data.append(E.versions(
                _pretty_print_xml(
                    frontik.app.get_frontik_and_apps_versions(self.application)
                )
            ))
        except Exception:
            debug_log.exception('cannot add version information')
            debug_log_data.append(E.versions('failed to get version information'))

        try:
            debug_log_data.append(E.status(
                _pretty_print_json(self.application.get_current_status())
            ))
        except Exception:
            debug_log.exception('cannot add status information')
            debug_log_data.append(E.status('failed to get status information'))

        debug_log_data.append(E.request(
            E.method(self.request.method),
            _params_to_xml(self.request.uri),
            _headers_to_xml(self.request.headers),
            _cookies_to_xml(self.request.headers)
        ))

        debug_log_data.append(E.response(
            _headers_to_xml(self.headers),
            _cookies_to_xml(self.headers)
        ))

        response_buffer = b''.join(self.chunks)
        original_response = {
            'buffer': base64.b64encode(response_buffer),
            'headers': dict(self.headers),
            'code': int(self.status_code)
        }

        debug_log_data.append(frontik.xml_util.dict_to_xml(original_response, 'original-response'))
        debug_log_data.set('response-size', str(len(response_buffer)))
        debug_log_data.set('generate-time', _format_number((time.time() - start_time) * 1000))

        for upstream in debug_log_data.xpath('//meta-info/upstream'):
            upstream.set('color', _string_to_color(upstream.get('name')))

        if not getattr(self.request, '_debug_inherited', False):
            try:
                transform = etree.XSLT(etree.parse(DEBUG_XSL))
                log_document = utf8(str(transform(debug_log_data)))
            except Exception:
                debug_log.exception('XSLT debug file error')

                try:
                    debug_log.error('XSL error log entries:\n' + '\n'.join(
                        '{0.filename}:{0.line}:{0.column}\n\t{0.message}'.format(m) for m in transform.error_log
                    ))
                except Exception:
                    pass

                log_document = etree.tostring(debug_log_data, encoding='UTF-8', xml_declaration=True)
        else:
            log_document = etree.tostring(debug_log_data, encoding='UTF-8', xml_declaration=True)

        return log_document


class DebugMode:
    def __init__(self, handler):
        debug_value = frontik.util.get_cookie_or_url_param_value(handler, 'debug')

        self.mode_values = debug_value.split(',') if debug_value is not None else ''
        self.inherited = handler.request.headers.get(DEBUG_HEADER_NAME)

        if self.inherited:
            debug_log.debug('debug mode is inherited due to %s request header', DEBUG_HEADER_NAME)
            handler.request._debug_inherited = True

        if debug_value is not None or self.inherited:
            handler.require_debug_access()

            self.enabled = handler.request._debug_enabled = True
            self.pass_debug = 'nopass' not in self.mode_values or self.inherited
            self.profile_xslt = 'xslt' in self.mode_values

            RequestContext.set('log_handler', DebugBufferedHandler())

            if self.pass_debug:
                debug_log.debug('%s header will be passed to all requests', DEBUG_HEADER_NAME)
        else:
            self.enabled = False
            self.pass_debug = False
            self.profile_xslt = False

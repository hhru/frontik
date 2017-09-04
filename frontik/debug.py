# coding=utf-8

import base64
import copy
import inspect
import logging
import os
import pprint
import time
import traceback
from datetime import datetime
from io import BytesIO

import lxml.etree as etree
import simplejson as json
from lxml.builder import E
from tornado.escape import to_unicode, utf8
from tornado.httpclient import HTTPResponse
from tornado.httputil import HTTPHeaders
from tornado.web import OutputTransform

import frontik.util
import frontik.xml_util
from frontik.compat import basestring_type, iteritems, SimpleCookie, unicode_type, urlparse
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
        if 'text/html' in content_type:
            body = frontik.util.decode_string_from_charset(response.body, try_charsets)
            body = body.replace('\r', '\\r').replace('\n', '\\n').replace("'", "\\'").replace("<", "&lt;")
        elif 'protobuf' in content_type:
            body = repr(response.body)
        elif response.body is None:
            body = ''
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
        for name, value in iteritems(response.time_info):
            time_info.append(E.time('{} ms'.format(value * 1000), name=name))
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
                body_query = urlparse.parse_qs(str(request.body), True)
                for name, values in iteritems(body_query):
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
        return string.replace(u"'", u"'\"'\"'")

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
        curl_echo_data = u"echo -e {} |".format(request_body)
        curl_data_string = u'--data-binary @-'
    else:
        curl_echo_data = ''
        curl_data_string = u"--data '{}'".format(request_body) if request_body else ''

    def _format_header(key):
        header_value = frontik.util.any_to_unicode(curl_headers[key])
        return u"-H '{0}: {1}'".format(key, _escape_apos(header_value))

    return u"{echo} curl -X {method} '{url}' {headers} {data}".format(
        echo=curl_echo_data,
        method=request.method,
        url=to_unicode(request.url),
        headers=u' '.join(_format_header(k) for k in sorted(curl_headers.keys())),
        data=curl_data_string
    ).strip()


def _params_to_xml(url):
    params = etree.Element('params')
    query = frontik.util.get_query_parameters(url)
    for name, values in iteritems(query):
        for value in values:
            try:
                params.append(E.param(to_unicode(value), name=to_unicode(name)))
            except UnicodeDecodeError:
                debug_log.exception('cannot decode parameter name or value')
                params.append(E.param(repr(value), name=repr(name)))
    return params


def _headers_to_xml(request_or_response_headers):
    headers = etree.Element('headers')
    for name, value in iteritems(request_or_response_headers):
        if name != 'Cookie':
            str_value = value if isinstance(value, basestring_type) else str(value)
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


class DebugBufferedHandler(BufferedHandler):
    FIELDS = ['created', 'filename', 'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
              'name', 'pathname', 'process', 'processName', 'relativeCreated', 'threadName']

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

        if getattr(record, '_labels', None) is not None:
            labels = E.labels()
            for label in record._labels:
                labels.append(E.label(label))
            entry.append(labels)

        if getattr(record, '_response', None) is not None:
            entry.append(response_to_xml(record._response))

        if getattr(record, '_request', None) is not None:
            entry.append(request_to_xml(record._request))

        if getattr(record, '_debug_response', None) is not None:
            entry.append(E.debug(record._debug_response))

        if getattr(record, '_xslt_profile', None) is not None:
            entry.append(record._xslt_profile)

        if getattr(record, '_xml', None) is not None:
            entry.append(E.text(etree.tostring(record._xml, encoding='unicode')))

        if getattr(record, '_protobuf', None) is not None:
            entry.append(E.text(unicode_type(record._protobuf)))

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
            headers = HTTPHeaders({'Content-Type': 'text/html'})
        else:
            headers = HTTPHeaders({
                'Content-Type': 'application/xml',
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
        debug_log_data.set('code', str(self.status_code))
        debug_log_data.set('started', _format_number(self.request._start_time))
        debug_log_data.set('request-id', str(self.request.request_id))
        debug_log_data.set('stages-total', _format_number((time.time() - self.request._start_time) * 1000))

        if hasattr(self.application.config, 'debug_labels') and isinstance(self.application.config.debug_labels, dict):
            debug_log_data.append(frontik.xml_util.dict_to_xml(self.application.config.debug_labels, 'labels'))

        try:
            debug_log_data.append(E.versions(
               _pretty_print_xml(
                    frontik.app.get_frontik_and_apps_versions(self.application)
               )
            ))
        except:
            debug_log.exception('cannot add version information')
            debug_log_data.append(E.versions('failed to get version information'))

        try:
            debug_log_data.append(E.status(
                _pretty_print_json(self.application.get_current_status())
            ))
        except:
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
            'code': self.status_code
        }

        debug_log_data.append(frontik.xml_util.dict_to_xml(original_response, 'original-response'))
        debug_log_data.set('response-size', str(len(response_buffer)))
        debug_log_data.set('generate-time', _format_number((time.time() - start_time) * 1000))

        if not getattr(self.request, '_debug_inherited', False):
            try:
                transform = etree.XSLT(etree.parse(DEBUG_XSL))
                log_document = utf8(str(transform(debug_log_data)))
            except Exception:
                debug_log.exception('XSLT debug file error')

                try:
                    debug_log.error('XSL error log entries:\n{}'.format('\n'.join(
                        '{0.filename}:{0.line}:{0.column}\n\t{0.message}'.format(m) for m in transform.error_log
                    )))
                except Exception:
                    pass

                log_document = etree.tostring(debug_log_data, encoding='UTF-8', xml_declaration=True)
        else:
            log_document = etree.tostring(debug_log_data, encoding='UTF-8', xml_declaration=True)

        return log_document


class DebugMode(object):
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
            debug_log.debug('debug mode is ON')

            if self.pass_debug:
                debug_log.debug('%s header will be passed to all requests', DEBUG_HEADER_NAME)
        else:
            self.enabled = False
            self.pass_debug = False
            self.profile_xslt = False

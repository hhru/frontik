# coding=utf-8

import Cookie
import inspect
import logging
import os
import pprint
import time
import traceback
import urlparse
import weakref
import copy
from datetime import datetime

import simplejson as json
import lxml.etree as etree
from lxml.builder import E
from tornado.escape import to_unicode
import tornado.options

import frontik.util
import frontik.xml_util

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
            body = body.replace('\n', '\\n').replace("'", "\\'").replace("<", "&lt;")
        elif 'json' in content_type:
            mode = 'json'
            body = _pretty_print_json(json.loads(response.body))
        elif 'protobuf' in content_type:
            body = response.body.encode('hex')
        elif response.body is None:
            body = ''
        elif 'xml' in content_type:
            mode = 'xml'
            body = _pretty_print_xml(etree.fromstring(response.body))
        else:
            if 'javascript' in content_type:
                mode = 'javascript'
            body = frontik.util.decode_string_from_charset(response.body, try_charsets)
    except Exception:
        debug_log.exception('Cannot parse response body')
        body = repr(response.body)

    try:
        for name, value in response.time_info.iteritems():
            time_info.append(E.time(str(value), name=name))
    except Exception:
        debug_log.exception('Cannot append time info')

    try:
        response = E.response(
            E.body(body, content_type=content_type, mode=mode),
            E.code(str(response.code)),
            E.effective_url(response.effective_url),
            E.error(str(response.error)),
            E.size(str(len(response.body)) if response.body is not None else '0'),
            E.request_time(str(int(response.request_time * 1000))),
            _headers_to_xml(response.headers),
            time_info,
        )
    except Exception:
        debug_log.exception('Cannot log response info')
        response = E.response(E.body('Cannot log response info'))
    return response


def request_to_xml(request):
    content_type = request.headers.get('Content-Type', '')
    body = etree.Element("body", content_type=content_type)

    if request.body:
        try:
            if 'json' in content_type:
                body.text = json.dumps(json.loads(request.body), sort_keys=True, indent=4)
            elif 'protobuf' in content_type:
                body.text = request.body.encode('hex')
            else:
                body_query = urlparse.parse_qs(str(request.body), True)
                for name, values in body_query.iteritems():
                    for value in values:
                        body.append(E.param(to_unicode(value), name=to_unicode(name)))
        except Exception:
            debug_log.exception('Cannot parse request body')
            body.text = repr(request.body)

    try:
        request = E.request(
            body,
            E.connect_timeout(str(request.connect_timeout)),
            E.follow_redirects(str(request.follow_redirects)),
            E.max_redirects(str(request.max_redirects)),
            E.method(request.method),
            E.request_timeout(str(request.request_timeout)),
            _params_to_xml(request.url),
            E.url(request.url),
            _headers_to_xml(request.headers),
            _cookies_to_xml(request.headers),
            E.meta(
                E.start_time(
                    str(request.start_time)
                ))
        )
    except Exception:
        debug_log.exception('Cannot parse request body')
        body.text = repr(request.body)
        request = E.request(body)
    return request


def _params_to_xml(url, logger=debug_log):
    params = etree.Element('params')
    query = frontik.util.get_query_parameters(url)
    for name, values in query.iteritems():
        for value in values:
            try:
                params.append(E.param(to_unicode(value), name=to_unicode(name)))
            except UnicodeDecodeError:
                logger.exception('Cannot decode parameter name or value')
                params.append(E.param(repr(value), name=repr(name)))
    return params


def _headers_to_xml(request_or_response_headers):
    headers = etree.Element('headers')
    for name, value in request_or_response_headers.iteritems():
        if name != 'Cookie':
            str_value = value if isinstance(value, basestring) else str(value)
            headers.append(E.header(to_unicode(str_value), name=name))
    return headers


def _cookies_to_xml(request_headers):
    cookies = etree.Element('cookies')
    if 'Cookie' in request_headers:
        _cookies = Cookie.SimpleCookie(request_headers['Cookie'])
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
            except IOError, e:
                lines, starting_line = [], None

            for i, l in enumerate(lines):
                line_node = etree.Element('line')
                line_node.append(E.text(to_unicode(l)))
                line_node.append(E.number(str(starting_line + i)))
                if starting_line + i == frame.f_lineno:
                    line_node.set('selected', 'true')
                trace_lines.append(line_node)

            trace_step_node.append(trace_lines)
            trace_step_node.append(E.file(inspect.getfile(frame)))
            trace_step_node.append(E.locals(pprint.pformat(frame.f_locals)))
            trace_node.append(trace_step_node)
            trace = trace.tb_next
        exc_node.append(trace_node)
    except Exception:
        log.exception('Could not add traceback lines')

    exc_node.append(E.text(''.join(traceback.format_exception(*exc_info))))
    return exc_node


def _pretty_print_xml(node):
    return etree.tostring(node, pretty_print=True, encoding=unicode)


def _pretty_print_json(node):
    return json.dumps(node, sort_keys=True, indent=4, ensure_ascii=False)


class DebugLogBulkHandler(object):
    FIELDS = ['created', 'filename', 'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
              'name', 'pathname', 'process', 'processName', 'relativeCreated', 'threadName']

    def __init__(self):
        self.log_data = etree.Element('log')

    def handle_bulk(self, record_list, **kwargs):
        for record in record_list:
            self.handle(record)

    def handle(self, record):
        entry_attrs = {}
        for field in self.FIELDS:
            val = getattr(record, field)
            if val is not None:
                entry_attrs[field] = str(val)

        entry_attrs['msg'] = to_unicode(record.getMessage())

        try:
            entry = etree.Element("entry", **entry_attrs)
        except ValueError:
            debug_log.exception('Error creating log entry with attrs: {0}'.format(entry_attrs))
            entry = etree.Element("entry")

        entry.set("asctime", str(datetime.fromtimestamp(record.created)))

        if record.exc_info is not None:
            entry.append(_exception_to_xml(record.exc_info))

        if getattr(record, '_labels', None) is not None:
            labels = E.labels()
            for label in record._labels:
                labels.append(E.label(label))
            entry.append(labels)

        if getattr(record, "_response", None) is not None:
            entry.append(response_to_xml(record._response))

        if getattr(record, "_request", None) is not None:
            entry.append(request_to_xml(record._request))

        if getattr(record, "_debug_response", None) is not None:
            entry.append(E.debug(record._debug_response))

        if getattr(record, '_xslt_profile', None) is not None:
            entry.append(record._xslt_profile)

        if getattr(record, "_xml", None) is not None:
            entry.append(E.text(_pretty_print_xml(record._xml)))

        if getattr(record, "_protobuf", None) is not None:
            entry.append(E.text(record._protobuf))

        if getattr(record, "_text", None) is not None:
            entry.append(E.text(record._text))

        self.log_data.append(entry)
        if getattr(record, "_stages", None) is not None:
            self.log_data.append(record._stages)


class PageHandlerDebug(object):
    DEBUG_HEADER_NAME = 'X-Hh-Debug'
    DEBUG_XSL = os.path.join(os.path.dirname(__file__), 'debug/debug.xsl')

    class DebugMode(object):
        def __init__(self, handler):
            debug_value = frontik.util.get_cookie_or_url_param_value(handler, 'debug')

            self.mode_values = debug_value.split(',') if debug_value is not None else ''
            self.inherited = handler.request.headers.get(PageHandlerDebug.DEBUG_HEADER_NAME)
            self.error_debug = False

            if debug_value is not None or self.inherited:
                self.enabled = True
                self.pass_debug = 'nopass' not in self.mode_values or self.inherited
                self.profile_xslt = 'xslt' in self.mode_values
            else:
                self.enabled = False
                self.pass_debug = False
                self.profile_xslt = False

            self.write_debug = tornado.options.options.debug or self.enabled

    def __init__(self, handler):
        self.handler = weakref.proxy(handler)
        self.debug_mode = PageHandlerDebug.DebugMode(self.handler)

        if self.debug_mode.enabled:
            self.handler.require_debug_access()
            self.handler.log.debug('debug mode is on')

        if self.debug_mode.write_debug:
            self.debug_log_handler = DebugLogBulkHandler()
            self.handler.log.add_bulk_handler(self.debug_log_handler, auto_flush=False)
            self.handler.log.debug('using debug mode logging')

        if self.debug_mode.inherited:
            self.handler.log.debug('debug mode is inherited due to {0} request header'.format(self.DEBUG_HEADER_NAME))

        if self.debug_mode.pass_debug:
            self.handler.log.debug('{0} header will be passed to all requests'.format(self.DEBUG_HEADER_NAME))

    def get_debug_page(self, status_code, response_headers, original_response=None):

        import frontik.app

        start_time = time.time()
        self.debug_log_handler.flush()

        debug_log_data = copy.deepcopy(self.debug_log_handler.log_data)
        debug_log_data.set('code', str(status_code))
        debug_log_data.set('mode', ','.join(self.debug_mode.mode_values))
        debug_log_data.set('started', str(self.handler.handler_started))
        debug_log_data.set('request-id', str(self.handler.request_id))

        if hasattr(self.handler.config, 'debug_labels') and isinstance(self.handler.config.debug_labels, dict):
            debug_log_data.append(frontik.xml_util.dict_to_xml(self.handler.config.debug_labels, 'labels'))

        debug_log_data.append(E.versions(
            _pretty_print_xml(frontik.app.get_frontik_and_apps_versions())
        ))

        debug_log_data.append(E.request(
            _params_to_xml(self.handler.request.uri, self.handler.log),
            _headers_to_xml(self.handler.request.headers),
            _cookies_to_xml(self.handler.request.headers)
        ))

        debug_log_data.append(E.response(_headers_to_xml(response_headers)))

        if getattr(self.handler, "_response_size", None) is not None:
            debug_log_data.set("response-size", str(self.handler._response_size))

        if original_response is not None:
            debug_log_data.append(frontik.xml_util.dict_to_xml(original_response, 'original-response'))

        debug_log_data.set('generate-time', str((time.time() - start_time) * 1000))

        # return raw xml if this is specified explicitly (noxsl=true) or when in inherited mode
        if frontik.util.get_cookie_or_url_param_value(self.handler, 'noxsl') is None and not self.debug_mode.inherited:
            try:
                transform = etree.XSLT(etree.parse(self.DEBUG_XSL))
                log_document = str(transform(debug_log_data))
                self.handler.set_header('Content-Type', 'text/html; charset=UTF-8')
            except Exception:
                self.handler.log.exception('XSLT debug file error')
                try:
                    self.handler.log.error('XSL error log entries:\n%s' % "\n".join(map(
                        'File "{0.filename}", line {0.line}, column {0.column}\n\t{0.message}'
                        .format, transform.error_log)))
                except Exception:
                    pass

                self.handler.set_header('Content-Type', 'application/xml; charset=UTF-8')
                log_document = etree.tostring(debug_log_data, encoding='UTF-8', xml_declaration=True)
        else:
            self.handler.set_header('Content-Type', 'application/xml; charset=UTF-8')
            log_document = etree.tostring(debug_log_data, encoding='UTF-8', xml_declaration=True)

        return log_document

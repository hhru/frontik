# -*- coding: utf-8 -*-

import Cookie
import logging
import traceback
import urlparse
import weakref
import simplejson as json
import copy
from datetime import datetime
import lxml.etree as etree
from lxml.builder import E
import tornado.options

import frontik.util
import frontik.xml_util

log = logging.getLogger('XML_debug')

def response_to_xml(response):
    time_info = etree.Element('time_info')
    content_type = response.headers.get('Content-Type', '')

    try:
        if 'text/html' in content_type:
            body = response.body.decode('utf-8').replace('\n', '\\n').replace("'", "\\'")
        elif 'json' in content_type:
            body = json.dumps(json.loads(response.body), sort_keys=True, indent=4)
        elif 'protobuf' in content_type:
            body = repr(response.body)
        elif 'text/plain' in content_type:
            body = response.body.decode("utf-8").replace("\n", "\\n").replace("'", "\\'")
        else:
            body = etree.fromstring(response.body)
    except Exception as e:
        body = 'Cant show response body, ' + str(e)

    for name, value in response.time_info.iteritems():
        time_info.append(E.time(str(value), name=name))

    return (
        E.response(
            E.body(body, content_type=content_type),
            E.code(str(response.code)),
            E.effective_url(response.effective_url),
            E.error(str(response.error)),
            E.size(str(len(response.body)) if response.body is not None else '0'),
            E.request_time(str(int(response.request_time * 1000))),
            _headers_to_xml(response.headers),
            time_info,
        )
    )

def request_to_xml(request):
    content_type = request.headers.get('Content-Type','')
    body = etree.Element("body", content_type = content_type)

    if request.body:
        try:
            if 'json' in content_type:
                body.text = json.dumps(json.loads(request.body), sort_keys = True, indent = 4)
            elif 'protobuf' in content_type:
                body.text = repr(request.body)
            else:
                body_query = urlparse.parse_qs(str(request.body), True)
                for name, values in body_query.iteritems():
                    for value in values:
                        body.append(E.param(value.decode("utf-8"), name = name))
        except Exception as e:
            body.text = 'Cant show request body, ' + str(e)

    return (
        E.request(
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
    )

def _params_to_xml(url):
    params = etree.Element('params')
    query = frontik.util.get_query_parameters(url)
    for name, values in query.iteritems():
        for value in values:
            params.append(E.param(unicode(value, 'utf-8'), name = name))
    return params

def _headers_to_xml(request_or_response_headers):
    headers = etree.Element('headers')
    for name, value in request_or_response_headers.iteritems():
        if name != 'Cookie':
            headers.append(E.header(str(value), name = name))
    return headers

def _cookies_to_xml(request_headers):
    cookies = etree.Element('cookies')
    if 'Cookie' in request_headers:
        _cookies = Cookie.SimpleCookie(request_headers['Cookie'])
        for cookie in _cookies:
            cookies.append(E.cookie(_cookies[cookie].value, name = cookie))
    return cookies


class DebugPageHandler(logging.Handler):
    def __init__(self):
        """
        Initializes the instance - basically setting the formatter to None
        and the filter list to empty.
        """
        logging.Filterer.__init__(self)
        self.level = logging.DEBUG
        self.formatter = None
        #get the module data lock, as we're updating a shared structure.
        self.createLock()

        self.log_data = etree.Element("log")

    FIELDS = ['created', 'filename', 'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
              'name', 'pathname', 'process', 'processName', 'relativeCreated', 'threadName']

    def handle(self, record):
        entry_attrs = {}
        for field in self.FIELDS:
            val = getattr(record, field)
            if val is not None:
                entry_attrs[field] = str(val)

        if record.exc_info is not None:
            exc = record.exc_info
            entry_attrs['exc_text'] = ''.join(traceback.format_exception(exc[0], exc[1], exc[2]))

        entry_attrs['msg'] = record.getMessage()

        entry = etree.Element("entry", **entry_attrs)
        entry.set("asctime", str(datetime.fromtimestamp(record.created)))

        if getattr(record, "_response", None) is not None:
            entry.append(response_to_xml(record._response))

        if getattr(record, "_request", None) is not None:
            entry.append(request_to_xml(record._request))

        if getattr(record, "_debug_response", None) is not None:
            entry.append(E.debug(record._debug_response))

        if getattr(record, "_xml", None) is not None:
            xml = etree.Element("xml")
            entry.append(xml)
            # make deepcopy
            # if node was sent to debug, but later was appended in some other place
            # etree will move node from this place to new one
            xml.append(copy.deepcopy(record._xml))

        if getattr(record, "_protobuf", None) is not None:
            entry.append(E.protobuf(record._protobuf))

        self.log_data.append(entry)
        if getattr(record, "_stages", None) is not None:
            self.log_data.append(record._stages)



class PageHandlerDebug(object):

    INHERIT_DEBUG_HEADER_NAME = 'X-Inherit-Debug'

    class DebugMode(object):
        def __init__(self, handler):
            debug_value = frontik.util.get_cookie_or_url_param_value(handler, 'debug')
            debug_params = None if debug_value is None else debug_value.split(',')
            has_debug_enable_param = debug_params is not None and filter(lambda x: x != 'profile', debug_params)

            self.inherited = handler.request.headers.get(PageHandlerDebug.INHERIT_DEBUG_HEADER_NAME)
            self.profile = debug_params is not None and 'profile' in debug_params

            if has_debug_enable_param or self.inherited:
                self.enabled = True
                self.return_response = (debug_params is not None and 'pass' in debug_params) or self.inherited
                self.pass_further = self.return_response
            else:
                self.enabled = False
                self.return_response = False
                self.pass_further = False

            self.write_debug = tornado.options.options.debug or self.enabled or self.profile


    def __init__(self, handler):
        self.handler = weakref.proxy(handler)
        self.debug_mode = PageHandlerDebug.DebugMode(self.handler)

        if self.debug_mode.enabled or self.debug_mode.profile:
            self.handler.require_debug_access()

        if self.debug_mode.enabled:
            self.handler.log.debug('debug mode is on')

        if self.debug_mode.write_debug:
            self.debug_log_handler = DebugPageHandler()
            self.handler.log.addHandler(self.debug_log_handler)
            self.handler.log.debug('using debug mode logging')

        if self.debug_mode.inherited:
            self.handler.log.debug('debug mode is inherited due to X-Inherit-Debug request header')

        if self.debug_mode.return_response:
            self.handler.log.debug('debug mode will be passed to all frontik apps requested (debug=pass)')

        if self.debug_mode.profile:
            self.profiler_options = {
                'warning-value': tornado.options.options.debug_profiler_warning_value,
                'critical-value': tornado.options.options.debug_profiler_critical_value
            }

    def get_profiler_template(self):
        try:
            with open(tornado.options.options.debug_profiler_template) as template:
                round_f = lambda x: '%.2f' % round(1000 * x, 2)
                data = json.dumps(dict([(x.name, {'start': round_f(x.start), 'delta': round_f(x.delta)})
                                        for x in self.handler.log.stages]))

                tpl_text = template.read()
                tpl_text = tpl_text.replace("'<%FrontikProfilerData%>'", data)
                tpl_text = tpl_text.replace("'<%FrontikProfilerOptions%>'", json.dumps(self.profiler_options))
                return tpl_text

        except IOError, e:
            self.handler.log.exception('Cannot find profiler template file')
            return None

    def get_debug_page(self, status_code, response_headers, original_response=None, finish_debug=True):
        if finish_debug:
            debug_log_data = self.debug_log_handler.log_data
        else:
            debug_log_data = copy.deepcopy(self.debug_log_handler.log_data)

        debug_log_data.set('code', str(status_code))
        debug_log_data.set('mode', self.handler.get_argument('debug', 'text'))
        debug_log_data.set('started', str(self.handler.handler_started))
        debug_log_data.set('request-id', str(self.handler.request_id))

        import frontik.app
        debug_log_data.append(frontik.app.get_frontik_and_apps_versions())
        debug_log_data.append(E.request(
            _params_to_xml(self.handler.request.uri),
            _headers_to_xml(self.handler.request.headers),
            _cookies_to_xml(self.handler.request.headers)))
        debug_log_data.append(E.response(_headers_to_xml(response_headers)))

        if getattr(self.handler, "_response_size", None) is not None:
            debug_log_data.set("response-size", str(self.handler._response_size))

        if self.debug_mode.return_response and original_response is not None:
            debug_log_data.append(frontik.xml_util.dict_to_xml(original_response, 'original-response'))

        # show debug page if apply_xsl=True ('noxsl' flag is not set)
        # if debug mode is disabled, than we could have got there only after an exception — apply xsl anyway
        # if debug mode is inherited (through X-Inherit-Debug request header), than the response is always xml
        can_apply_xsl_or_500 = self.handler.xml.apply_xsl or not self.debug_mode.enabled
        if can_apply_xsl_or_500 and not self.debug_mode.inherited:
            try:
                with open(tornado.options.options.debug_xsl) as xsl_file:
                    tranform = etree.XSLT(etree.XML(xsl_file.read()))
                log_document = str(tranform(debug_log_data))
                self.handler.set_header('Content-Type', 'text/html; charset=UTF-8')
            except Exception, e:
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

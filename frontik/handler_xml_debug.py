# -*- coding: utf-8 -*-

import Cookie
import inspect
import logging
import os.path
import time
import traceback
import urlparse
import weakref
import xml.sax.saxutils
import json
import copy
from datetime import datetime
import frontik.handler

import lxml.etree as etree
import tornado.options
from lxml.builder import E
from frontik.util import get_cookie_or_url_param_value
from frontik.xml_util import dict_to_xml


log = logging.getLogger('XML_debug')

def response_to_xml(response):
    headers = etree.Element("headers")
    time_info = etree.Element("time_info")

    if 'text/html' in response.headers.get('Content-Type',''):
        try:
            body = response.body.decode("utf-8").replace("\n", "\\n").replace("'", "\\'")
        except Exception as e:
            body = 'Cant show response body, ' + str(e)
    else:
        try:
            body = etree.fromstring(response.body)
        except Exception as e:
            body = 'Cant show response body, ' + str(e)

    for name, value in response.headers.iteritems():
        headers.append(E.header(value, name = name))

    for name, value in response.time_info.iteritems():
        time_info.append(E.time(str(value), name = name))

    return (
        E.response(
            E.body(body, content_type=response.headers.get('Content-Type','')),
            E.code(str(response.code)),
            E.effective_url(response.effective_url),
            E.error(str(response.error)),
            E.size(str(len(response.body)) if response.body is not None else '0'),
            E.request_time(str(int(response.request_time * 1000))),
            headers,
            time_info,
        )
    )


def request_to_xml(request):
    headers = etree.Element("headers")

    for name, value in request.headers.iteritems():
        if name != "Cookie":
            headers.append(E.header(str(value), name = name))


    cookies = etree.Element("cookies")
    if "Cookie" in request.headers:
        _cookies = Cookie.SimpleCookie(request.headers["Cookie"])
        for cookie in _cookies:
            cookies.append(E.cookie(_cookies[cookie].value, name = cookie))

    params = etree.Element("params")
    query = urlparse.parse_qs(urlparse.urlparse(request.url).query, True)
    for name, values in query.iteritems():
        for value in values:
            params.append(E.param(unicode(value, "utf-8"), name = name))

    body = etree.Element("body", content_type = request.headers.get('Content-Type',''))
    if request.body:
        if 'json' in request.headers.get('Content-Type',''):
            try:
                body.text = json.dumps(json.loads(request.body), sort_keys=True, indent=4)
            except Exception as e:
                body.text = "Cant show request body, " + str(e)
        else:
            try:
                body_query = urlparse.parse_qs(str(request.body), True)
                for name, values in body_query.iteritems():
                    for value in values:
                        body.append(E.param(value.decode("utf-8"), name = name))
            except Exception as e:
                body.text = "Cant show request body, " + str(e)

    return (
        E.request(
            body,
            E.connect_timeout(str(request.connect_timeout)),
            E.follow_redirects(str(request.follow_redirects)),
            E.max_redirects(str(request.max_redirects)),
            E.method(request.method),
            E.request_timeout(str(request.request_timeout)),
            params,
            E.url(request.url),
            headers,
            cookies
        )
    )


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

    FIELDS = ['created', 'filename', 'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs', 'name', 'pathname', 'process', 'processName', 'relativeCreated', 'threadName']
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

        self.log_data.append(entry)


class PageHandlerDebug(object):
    def __init__(self, handler):
        self.handler = weakref.proxy(handler)
        debug_enabled = get_cookie_or_url_param_value(self.handler, 'debug')
        self.debug_mode_inherited = self.handler.request.headers.get(frontik.handler.PageHandler.INHERIT_DEBUG_HEADER_NAME)
        self.debug_return_response = debug_enabled == 'pass' or self.debug_mode_inherited
        self.pass_debug_mode_further = self.debug_return_response

        if debug_enabled is not None or self.debug_mode_inherited:
            self.handler.require_debug_access()
            self.handler.log.debug('debug mode is on')
            self.debug_mode = True
        else:
            self.debug_mode = False

        if tornado.options.options.debug or self.debug_mode:
            self.debug_mode_logging = True
            self.debug_log_handler = DebugPageHandler()
            self.handler.log.addHandler(self.debug_log_handler)
            self.handler.log.debug('using debug mode logging')
        else:
            self.debug_mode_logging = False

        if self.debug_mode_inherited:
            self.handler.log.debug('debug mode is inherited due to X-Inherit-Debug request header')

        if self.debug_return_response:
            self.handler.log.debug('debug mode will be passed to all frontik apps requested (debug=pass)')

    def get_debug_page(self, status_code, original_response=None, **kwargs):
        self.debug_log_handler.log_data.set("code", str(status_code))
        self.debug_log_handler.log_data.set("mode", self.handler.get_argument('debug', 'text'))
        self.debug_log_handler.log_data.set("request-id", str(self.handler.request_id))

        if getattr(self.handler, "_response_size", None) is not None:
            self.debug_log_handler.log_data.set("response-size", str(self.handler._response_size))

        if self.debug_return_response and original_response is not None:
            self.debug_log_handler.log_data.append(dict_to_xml(original_response, 'original-response'))

        # show debug page if apply_xsl=True ('noxsl' flag is not set) or if 500 error occured
        # if debug mode is inherited (through X-Inherit-Debug request header), than the response is always xml
        if (self.handler.xml.apply_xsl or not self.debug_mode) and not self.debug_mode_inherited:
            try:
                xsl_file = open(tornado.options.options.debug_xsl)
                tranform = etree.XSLT(etree.XML(xsl_file.read()))
                xsl_file.close()
                log_document = str(tranform(self.debug_log_handler.log_data))
                self.handler.set_header('Content-Type', 'text/html; charset=UTF-8')
            except Exception, e:
                self.handler.log.exception('XSLT debug file error')
                self.handler.set_header('Content-Type', 'application/xml; charset=UTF-8')
                log_document = etree.tostring(self.debug_log_handler.log_data, encoding = 'UTF-8',
                                              xml_declaration = True)
        else:
            self.handler.set_header('Content-Type', 'application/xml; charset=UTF-8')
            log_document = etree.tostring(self.debug_log_handler.log_data, encoding = 'UTF-8', xml_declaration = True)

        return log_document

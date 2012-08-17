# -*- coding: utf-8 -*-

import Cookie
import inspect
from itertools import imap
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

import lxml.etree as etree
import tornado.options
from lxml.builder import E
from frontik.util import get_query_parameters


log = logging.getLogger('XML_debug')

def response_to_xml(response):
    headers = etree.Element("headers")
    time_info = etree.Element("time_info")
    content_type = response.headers.get('Content-Type','')

    if 'text/html' in content_type:
        try:
            body = response.body.decode("utf-8").replace("\n", "\\n").replace("'", "\\'")
        except Exception as e:
            body = 'Cant show response body, ' + str(e)
    else:
        try:
            if 'json' in content_type:
                body = json.dumps(json.loads(response.body), sort_keys = True, indent = 4)
            elif 'protobuf' in content_type:
                body = repr(response.body)
            elif 'text/plain' in content_type:
                body = response.body
            else:
                body = etree.fromstring(response.body)
        except Exception as e:
            body = 'Cant show response body, ' + str(e)

    for name, value in response.headers.iteritems():
        headers.append(E.header(value, name = name))

    for name, value in response.time_info.iteritems():
        time_info.append(E.time(str(value), name = name))

    return (
        E.response(
            E.body(body, content_type = content_type),
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
    query = get_query_parameters(request.url)
    for name, values in query.iteritems():
        for value in values:
            params.append(E.param(unicode(value, "utf-8"), name = name))

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


class PageHandlerDebug(object):
    def __init__(self, handler):
        self.handler = weakref.proxy(handler)

        if self.handler.get_argument('debug', None) is not None or self.handler.get_cookie("debug") is not None:
            self.handler.require_debug_access()
            self.handler.log.debug('debug mode is on due to ?debug query arg')
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
    def get_debug_page(self, status_code, **kwargs):
        self.debug_log_handler.log_data.set("code", str(status_code))
        self.debug_log_handler.log_data.set("mode", self.handler.get_argument('debug', 'text'))
        self.debug_log_handler.log_data.set("request-id", str(self.handler.request_id))

        response_size = sum(imap(len, self.handler._write_buffer))
        if hasattr(self.handler, '_finish_chunk_size'):
            response_size += self.handler._finish_chunk_size
        self.debug_log_handler.log_data.set("response-size", str(response_size))


        # if we have 500 but have "noxsl" in args without "debug" in args
        # apply xsl for debug info anyway
        if self.handler.xml.apply_xsl or not self.debug_mode:
            # show 'awesome' debug page
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

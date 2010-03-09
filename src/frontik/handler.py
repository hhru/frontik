# -*- coding: utf-8 -*-

from __future__ import with_statement

import os.path
import traceback
import urllib

from functools import partial

import tornado.autoreload
import tornado.web
import tornado.httpclient
import tornado.options

import frontik.util
from frontik import etree
from frontik.doc import Doc

import logging
log = logging.getLogger('frontik.handler')
log_xsl = logging.getLogger('frontik.handler.xsl')

import future
http_client = tornado.httpclient.AsyncHTTPClient(max_clients=200, max_simultaneous_connections=200)

def http_header_out(*args, **kwargs):
    log_xsl.debug('x:http-header-out called')

def set_http_status(*args, **kwargs):
    log_xsl.debug('x:set-http-status called')

def x_urlencode(context, params):
    log_xsl.debug('x:urlencode called')
    if params:
        return urllib.quote(params[0].text.encode("utf8") or "")

# TODO cleanup this
ns = etree.FunctionNamespace('http://www.yandex.ru/xscript')
ns.prefix = 'x'
ns['http-header-out'] = http_header_out
ns['set-http-status'] = set_http_status
ns['urlencode'] = x_urlencode

class ResponsePlaceholder(future.FutureVal):
    def __init__(self):
        pass

    def set_response(self, handler, response, callback=None):
        self.response = response
        self.callback = callback

        if response.error:
            handler.log.warn('%s failed %s', response.code, response.effective_url)

    def get(self):
        if not self.response.error:
            try:
                element = etree.fromstring(self.response.body)

                if self.callback:
                    self.callback(element)
                return [etree.Comment(self.response.effective_url), element]
            except:
                return etree.Element('error', dict(url=self.response.effective_url, reason='invalid XML'))
        else:
            return etree.Element('error', dict(url=self.response.effective_url, reason=self.response.error.message))

class Stats:
    def __init__(self):
        self.page_count = 0
        self.http_reqs_count = 0

stats = Stats()

class PageLogger(object):
    '''
    This class is supposed to fix huge memory 'leak' in logging
    module. I.e. every call to logging.getLogger(some_unique_name)
    wastes memory as resulting logger is memoized by
    module. PageHandler used to create unique logger on each request
    by call logging.getLogger('frontik.handler.%s' %
    (self.request_id,)). This lead to wasting about 10Mb per 10K
    requests.
    '''
    
    def __init__(self, request_id):
        self.request_id = request_id

    def _proxy_method(method_name):
        def proxy(self, msg, *args):
            return getattr(log, method_name)('{%s} %s' % (self.request_id, msg), *args)
        return proxy

    debug = _proxy_method('debug')
    info = _proxy_method('info')
    warn = _proxy_method('warn')
    error = _proxy_method('error')
    critical = _proxy_method('critical')
    exception = _proxy_method('exception')


class PageHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kw):
        tornado.web.RequestHandler.__init__(self, *args, **kw)
        
        self.doc = Doc()
        self.n_waiting_reqs = 0
        self.finishing = False
        self.transform = None
        
        self.request_id = self.request.headers.get('X-Request-Id', self.get_next_request_id())
        
        self.log = PageLogger(self.request_id)
        
        self.log.debug('started %s %s', self.request.method, self.request.uri)

    
    @classmethod
    def get_next_request_id(cls):
        stats.page_count += 1
        return stats.page_count

    def fetch_url(self, url, callback=None): #TODO вычистить
        placeholder = ResponsePlaceholder()
        self.n_waiting_reqs += 1
        stats.http_reqs_count += 1
        
        http_client.fetch(
            tornado.httpclient.HTTPRequest(
                url=url,
                headers={
                    'Connection':'Keep-Alive',
                    'Keep-Alive':'1000'}), 
            self.async_callback(partial(self._fetch_url_response, placeholder, callback)))
        
        return placeholder

    def get_url(self, url, data={}, callback=None):
        placeholder = ResponsePlaceholder()
        self.n_waiting_reqs += 1
        stats.http_reqs_count += 1

        http_client.fetch(
            tornado.httpclient.HTTPRequest(
                url=frontik.util.make_url(url, **data),
                headers={
                    'Connection':'Keep-Alive',
                    'Keep-Alive':'1000'}),
            self.async_callback(partial(self._fetch_url_response, placeholder, callback)))
        return placeholder
        

    def post_url(self, url, data={}, headers={}, callback=None):
        placeholder = ResponsePlaceholder()
        self.n_waiting_reqs += 1
        stats.http_reqs_count += 1

        http_client.fetch(
            tornado.httpclient.HTTPRequest(
                method='POST',
                url=url,
                body=frontik.util.make_qs(data),
                headers={
                    'Connection':'Keep-Alive',
                    'Keep-Alive':'1000',
                    'Content-Type' : 'application/x-www-form-urlencoded'}),
            self.async_callback(partial(self._fetch_url_response, placeholder, callback)))
        return placeholder

    def _fetch_url_response(self, placeholder, callback, response):
        self.n_waiting_reqs -= 1
        self.log.debug('got %s %s in %.3f, %s requests pending', response.code, response.effective_url, response.request_time, self.n_waiting_reqs)
        
        placeholder.set_response(self, response, callback)
        self._try_finish_page()

    def finish_page(self):
        self.log.debug('going to finish')
        
        self.finishing = True
        self._try_finish_page()
    
    def _try_finish_page(self):
        if self.finishing and self.n_waiting_reqs == 0:
            if (self.transform):
                self._real_finish_with_xsl()
            else:
                self._real_finish()

    def _real_finish_with_xsl(self):
        self.log.debug('finishing with xsl')
        self.set_header('Content-Type', 'text/html')

        try:
            result = str(self.transform(self.doc.to_etree_element()))
            self.log.debug('applying XSLT %s', self.transform_filename)
        except:
            result = ""
            self.log.exception('failed transformation with XSL %s' % self.transform_filename)

        self.write(result)
        self.log.debug('done')
        self.finish('')

    
    def _real_finish(self):
        self.log.debug('finishing wo xsl')

        self.set_header('Content-Type', 'application/xml')

        self.write(self.doc.to_string())

        self.log.debug('done')

        self.finish('')

    ###
    xml_files_cache = dict()

    def xml_from_file(self, filename):
        if filename in self.xml_files_cache:
            self.log.debug('got %s file from cache', filename)
            return self.xml_files_cache[filename]
        else:
            ok, ret = self._xml_from_file(filename)

            if ok:
                self.xml_files_cache[filename] = ret

            return [etree.Comment('file: %s' % (filename,)),
                    ret]

    def _xml_from_file(self, filename):
        real_filename = os.path.join(self.request.config.XML_root, filename)
        self.log.debug('read %s file from %s', filename, real_filename)

        if os.path.exists(real_filename):
            try:
                res = etree.parse(file(real_filename)).getroot()

                tornado.autoreload.watch_file(real_filename)
                
                return True, res
            except:
                return False, etree.Element('error', dict(msg='failed to parse file: %s' % (filename,)))
        else:
            return False, etree.Element('error', dict(msg='file not found: %s' % (filename,)))

    ###
    xsl_files_cache = dict()

    def set_xsl(self, filename):
        if not self.request.config.apply_xsl or self.get_argument('noxsl', None):
            return

        real_filename = os.path.join(self.request.config.XSL_root, filename)

        def gen_transformation():
            tree = etree.parse(fp)
            self.log.debug('parsed XSL file %s', real_filename)
            transform = etree.XSLT(tree)
            self.log.debug('generated transformation from XSL file %s', real_filename)
            return transform

        try:
            if self.xsl_files_cache.has_key(real_filename):
                self.transform = self.xsl_files_cache[real_filename]
            else:
                with open(real_filename, "rb") as fp:
                    self.log.debug('read file %s', real_filename)
                    tree = etree.parse(fp)
                    self.transform = etree.XSLT(tree)
                    self.xsl_files_cache[real_filename] = self.transform
                tornado.autoreload.watch_file(real_filename)
        except etree.XMLSyntaxError, error:
            self.log.exception('failed parsing XSL file {0} (XML syntax)'.format(real_filename))
            raise tornado.web.HTTPError(500, 'failed parsing XSL file %s (XML syntax)', real_filename)
        except etree.XSLTParseError, error:
            self.log.exception('failed parsing XSL file {0} (dumb xsl)'.format(real_filename))
            raise tornado.web.HTTPError(500, 'failed parsing XSL file %s (dumb xsl)', real_filename)
        except:
            self.log.exception('XSL transformation error with file %s' % real_filename)
            raise tornado.web.HTTPError(500)
        self.transform_filename = real_filename

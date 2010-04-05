# -*- coding: utf-8 -*-

from __future__ import with_statement

import os.path
import urllib

from functools import partial

import tornado.autoreload
import tornado.web
import tornado.httpclient
import tornado.options

import frontik.util
from frontik import etree
from frontik.doc import Doc

import xml_util

import logging
log = logging.getLogger('frontik.handler')
log_xsl = logging.getLogger('frontik.handler.xsl')
log_fileloader = logging.getLogger('frontik.server.fileloader')

import future

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

    def set_response(self, handler, response):
        '''
        return :: response_as_xml

        None - в случае ошибки парсинга
        '''
        self.response = response

        ret = None

        if response.error:
            handler.log.warn('%s failed %s', response.code, response.effective_url)
            self.data = etree.Element('error', dict(url=self.response.effective_url, reason=self.response.error.message))
        else:
            try:
                element = etree.fromstring(self.response.body)
                self.data = [etree.Comment(self.response.effective_url), element]
                ret = element
            except:
                self.data = etree.Element('error', dict(url=self.response.effective_url, reason='invalid XML'))

        return ret

    def get(self):
        return self.data

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


class FileCache:
    def __init__(self, root_dir, load_fn):
        '''
        load_fn :: filename -> (status, result)
        '''

        self.root_dir = root_dir
        self.load_fn = load_fn

        self.cache = dict()

    def load(self, filename):
        if filename in self.cache:
            log_fileloader.debug('got %s file from cache', filename)
            return self.cache[filename]
        else:
            real_filename = os.path.normpath(os.path.join(self.root_dir, filename))

            log_fileloader.debug('reading %s file from %s', filename, real_filename)
            ok, ret = self.load_fn(real_filename)

        if ok:
            self.cache[filename] = ret

        return ret


def xml_from_file(filename):
    ''' 
    filename -> (status, et.Element)

    status == True - результат хороший можно кешировать
           == False - результат плохой, нужно вернуть, но не кешировать
    '''

    if os.path.exists(filename):
        try:
            res = etree.parse(file(filename)).getroot()
            tornado.autoreload.watch_file(filename)

            return True, [etree.Comment('file: %s' % (filename,)), res]
        except:
            log.exception('failed to parse %s', filename)
            return False, etree.Element('error', dict(msg='failed to parse file: %s' % (filename,)))
    else:
        log.error('file not found: %s', filename)
        return False, etree.Element('error', dict(msg='file not found: %s' % (filename,)))


def xsl_from_file(filename):
    '''
    filename -> (True, et.XSLT)
    
    в случае ошибки выкидывает исключение
    '''

    transform, xsl_files = xml_util.read_xsl(filename)
    
    for xsl_file in xsl_files:
        tornado.autoreload.watch_file(xsl_file)

    return True, transform


class InvalidOptionCache:
    def __init__(self, option):
        self.option = option

    def load(self, filename):
        raise Exception('{0} option is undefined'.format(self.option))


def make_file_cache(option_name, option_value, fun):
    if option_value:
        return FileCache(option_value, fun)
    else:
        return InvalidOptionCache(option_name)


class PageHandlerGlobals:
    '''
    Объект с настройками для всех хендлеров
    '''
    def __init__(self, app_package):
        self.config = app_package.config

        self.xml_cache = make_file_cache('XML_root', getattr(app_package.config, 'XML_root', None), xml_from_file)
        self.xsl_cache = make_file_cache('XML_root', getattr(app_package.config, 'XSL_root', None), xsl_from_file)


class PageHandler(tornado.web.RequestHandler):
    '''
    Хендлер для конкретного запроса. Создается на каждый запрос.
    '''
    
    def __init__(self, ph_globals, application, request):
        tornado.web.RequestHandler.__init__(self, application, request)

        self.config = ph_globals.config
        self.xml_cache = ph_globals.xml_cache
        self.xsl_cache = ph_globals.xsl_cache

        self.doc = Doc()
        self.n_waiting_reqs = 0
        self.finishing = False
        self.transform = None
        
        self.request_id = self.request.headers.get('X-Request-Id', self.get_next_request_id())

        self.http_client = tornado.httpclient.AsyncHTTPClient(max_clients=200, max_simultaneous_connections=200)

        
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
        
        self.http_client.fetch(
            tornado.httpclient.HTTPRequest(
                url=url,
                headers={
                    'Connection':'Keep-Alive',
                    'Keep-Alive':'1000'}), 
            self.async_callback(partial(self._fetch_url_response, placeholder, callback)))
        
        return placeholder

    def get_url(self, url, data={}, connect_timeout=0.5, request_timeout=0.5, callback=None):
        placeholder = ResponsePlaceholder()
        self.n_waiting_reqs += 1
        stats.http_reqs_count += 1

        self.http_client.fetch(
            tornado.httpclient.HTTPRequest(
                url=frontik.util.make_url(url, **data),
                headers={
                    'Connection':'Keep-Alive',
                    'Keep-Alive':'1000'},
                connect_timeout=connect_timeout,
                request_timeout=request_timeout),
            self.async_callback(partial(self._fetch_url_response, placeholder, callback)))
        return placeholder
        

    def post_url(self,
                 url,
                 data={},
                 headers={},
                 files={},
                 connect_timeout=0.5, request_timeout=0.5,
                 callback=None):
        
        placeholder = ResponsePlaceholder()
        
        self.n_waiting_reqs += 1
        stats.http_reqs_count += 1
        
        body, content_type = frontik.util.make_mfd(data, files) if files else (frontik.util.make_qs(data), 'application/x-www-form-urlencoded')
        
        headers = {'Connection':'Keep-Alive',
                   'Keep-Alive':'1000',
                   'Content-Type' : content_type,
                   'Content-Length': str(len(body))}

        self.http_client.fetch(
            tornado.httpclient.HTTPRequest(
                method='POST',
                url=url,
                body=body,
                headers=headers,
                connect_timeout=connect_timeout,
                request_timeout=request_timeout),
            self.async_callback(partial(self._fetch_url_response, placeholder, callback)))
        return placeholder

    def _fetch_url_response(self, placeholder, callback, response):
        self.n_waiting_reqs -= 1
        self.log.debug('got %s %s in %.3f, %s requests pending', response.code, response.effective_url, response.request_time, self.n_waiting_reqs)
        
        xml = placeholder.set_response(self, response)

        if callback:
            callback(xml, response)

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
        if not self.request.headers.get("Content-Type", None):
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
        if not self.request.headers.get("Content-Type", None):
            self.set_header('Content-Type', 'application/xml')

        self.write(self.doc.to_string())

        self.log.debug('done')

        self.finish('')

    ###
    def xml_from_file(self, filename):
        return self.xml_cache.load(filename)


    def _set_xsl_log_and_raise(self, msg_template):
        msg = msg_template.format(self.transform_filename)
        self.log.exception(msg)
        raise tornado.web.HTTPError(500, msg)

    def set_xsl(self, filename):
        if not self.config.apply_xsl:
            self.log.debug('ignored set_xsl(%s) because config.apply_xsl=%s', filename, self.config.apply_xsl)        
            return

        if self.get_argument('noxsl', None):
            self.log.debug('ignored set_xsl(%s) because noxsl=%s', filename, self.get_argument('noxsl'))
            return
                           
        self.transform_filename = filename

        try:
            self.transform = self.xsl_cache.load(filename)

        except etree.XMLSyntaxError, error:
            self._set_xsl_log_and_raise('failed parsing XSL file {0} (XML syntax)')
        except etree.XSLTParseError, error:
            self._set_xsl_log_and_raise('failed parsing XSL file {0} (dumb xsl)')
        except:
            self._set_xsl_log_and_raise('XSL transformation error with file {0}')

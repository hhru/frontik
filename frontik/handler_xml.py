# -*- coding: utf-8 -*-

import functools
import os.path
import threading
import time
import urllib
import weakref

import lxml.etree as etree
import tornado.autoreload
import tornado.options
import tornado.ioloop

import frontik.util
import frontik.auth
import frontik.xml_util

import logging
log = logging.getLogger('frontik.server')
log_xsl = logging.getLogger('frontik.handler.xsl')
log_fileloader = logging.getLogger('frontik.server.fileloader')

# xsl global functions
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


class FileCache(object):
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


def _source_comment(src):
    return etree.Comment('Source: {0}'.format(frontik.util.asciify_url(src).replace('--', '%2D%2D')))

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

            return True, [_source_comment(filename), res]
        except:
            log_fileloader.exception('failed to parse %s', filename)
            return False, etree.Element('error', dict(msg = 'failed to parse file: %s' % (filename,)))
    else:
        log_fileloader.error('file not found: %s', filename)
        return False, etree.Element('error', dict(msg = 'file not found: %s' % (filename,)))


def xsl_from_file(filename):
    '''
    filename -> (True, et.XSLT)
    
    в случае ошибки выкидывает исключение
    '''

    transform, xsl_files = frontik.xml_util.read_xsl(filename)

    for xsl_file in xsl_files:
        tornado.autoreload.watch_file(xsl_file)

    return True, transform


class InvalidOptionCache(object):
    def __init__(self, option):
        self.option = option

    def load(self, filename):
        raise Exception('{0} option is undefined'.format(self.option))


def make_file_cache(option_name, option_value, fun):
    if option_value:
        return FileCache(option_value, fun)
    else:
        return InvalidOptionCache(option_name)


class PageHandlerXMLGlobals(object):
    def __init__(self, config):
        for schema, path in getattr(config, 'XSL_SCHEMAS', {}).items():
            frontik.xml_util.parser.resolvers.add(
                frontik.xml_util.PrefixResolver(schema, path))
        self.xml_cache = make_file_cache('XML_root', getattr(config, 'XML_root', None), xml_from_file)
        self.xsl_cache = make_file_cache('XSL_root', getattr(config, 'XSL_root', None), xsl_from_file)


class PageHandlerXML(object):
    def __init__(self, handler):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)

        self.xml_cache = self.handler.ph_globals.xml.xml_cache
        self.xsl_cache = self.handler.ph_globals.xml.xsl_cache

        self.doc = frontik.doc.Doc(root_node = etree.Element('doc', frontik = 'true'))
        self.transform = None
        if not self.handler.config.apply_xsl:
            self.log.debug('ignoring set_xsl() because config.apply_xsl=%s', self.handler.config.apply_xsl)
            self.apply_xsl = False

        elif self.handler.get_argument('noxsl', None) is not None or self.handler.get_cookie("noxsl") is not None:
            self.handler.require_debug_access()
            self.apply_xsl = False
            self.log.debug('apply_xsl==False due to ?noxsl query arg')
        else:
            self.apply_xsl = True

    def xml_from_file(self, filename):
        return self.xml_cache.load(filename)

    def _set_xsl_log_and_raise(self, msg_template):
        msg = msg_template.format(self.transform_filename)
        self.handler.log.exception(msg)
        raise tornado.web.HTTPError(500, msg)

    def set_xsl(self, filename):
        self.transform_filename = filename

        try:
            self.transform = self.xsl_cache.load(filename)

        except etree.XMLSyntaxError, error:
            self._set_xsl_log_and_raise('failed parsing XSL file {0} (XML syntax)')
        except etree.XSLTParseError, error:
            self._set_xsl_log_and_raise('failed parsing XSL file {0} (XSL parse error)')
        except:
            self._set_xsl_log_and_raise('XSL transformation error with file {0}')

    def _finish_xml(self):
        if self.apply_xsl and self.transform:
            return self._prepare_finish_with_xsl()
        else:
            return self._prepare_finish_wo_xsl()

    def _prepare_finish_with_xsl(self):
        self.log.debug('finishing with xsl')

        if not self.handler._headers.get("Content-Type", None):
            self.handler.set_header('Content-Type', 'text/html')

        try:
            t = time.time()
            result = str(self.transform(self.doc.to_etree_element()))
            self.log.stage_tag("xsl")
            self.log.debug('applied XSL %s in %.2fms', self.transform_filename, (time.time() - t)*1000)
            self.log.debug('xsl messages: %s' % " ".join(map("message: {0.message}".format, self.transform.error_log)))
            return result
        except:
            self.log.exception('failed transformation with XSL %s' % self.transform_filename)
            self.log.exception('error_log entries: %s' % "\n".join(map("message from line: {0.line}, column: {0.column}, \
            domain: {0.domain_name}, type: {0.type_name}\
            level: {0.level_name}, file : {0.filename}, message: {0.message}".format, self.transform.error_log)))
            raise

    def _prepare_finish_wo_xsl(self):
        self.log.debug('finishing wo xsl')

        # В режиме noxsl мы всегда отдаем xml.
        self.handler.set_header('Content-Type', 'application/xml')

        return self.doc.to_string()

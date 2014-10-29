# coding=utf-8

import copy
import time
import weakref

from lxml import etree
import tornado.options

import frontik.doc
import frontik.file_cache
import frontik.jobs
import frontik.util
from frontik.xml_util import xml_from_file, xsl_from_file


class ApplicationXMLGlobals(object):
    def __init__(self, config):
        self.xml_cache = frontik.file_cache.make_file_cache(
            'XML', 'XML_root',
            getattr(config, 'XML_root', None),
            xml_from_file,
            getattr(config, 'XML_cache_limit', None),
            getattr(config, 'XML_cache_step', None),
            deepcopy=True
        )

        self.xsl_cache = frontik.file_cache.make_file_cache(
            'XSL', 'XSL_root',
            getattr(config, 'XSL_root', None),
            xsl_from_file,
            getattr(config, 'XSL_cache_limit', None),
            getattr(config, 'XSL_cache_step', None)
        )


class XmlProducer(object):
    def __init__(self, handler, xml_globals):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)
        self.executor = frontik.jobs.get_executor(tornado.options.options.xsl_executor)

        self.xml_cache = xml_globals.xml_cache
        self.xsl_cache = xml_globals.xsl_cache

        self.doc = frontik.doc.Doc(root_node=etree.Element('doc', frontik='true'))
        self.transform = None
        self.transform_filename = None

    def __call__(self, callback):
        if any(frontik.util.get_cookie_or_url_param_value(self.handler, p) is not None for p in ('noxsl', 'notpl')):
            self.handler.require_debug_access()
            self.log.debug('ignoring XSLT because noxsl/notpl parameter is passed')
            self._finish_with_xml(callback)
            return

        if not self.transform_filename:
            self._finish_with_xml(callback)
            return

        try:
            self.transform = self.xsl_cache.load(self.transform_filename, self.log)
        except etree.XMLSyntaxError:
            self.log.error('failed parsing XSL file %s (XML syntax)', self.transform_filename)
            raise
        except etree.XSLTParseError:
            self.log.error('failed parsing XSL file %s (XSL parse error)', self.transform_filename)
            raise
        except:
            self.log.error('failed loading XSL file %s', self.transform_filename)
            raise

        self._finish_with_xslt(callback)

    def set_xsl(self, filename):
        self.transform_filename = filename

    def _finish_with_xslt(self, callback):
        self.log.debug('finishing with XSLT')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'text/html; charset=utf-8')

        def job():
            start_time = time.time()
            result = self.transform(copy.deepcopy(self.doc.to_etree_element()),
                                    profile_run=self.handler.debug.debug_mode.profile_xslt)
            return start_time, str(result), result.xslt_profile

        def success_cb(result):
            start_time, xml_result, xslt_profile = result

            self.log.info('applied XSL %s in %.2fms', self.transform_filename, (time.time() - start_time) * 1000)

            if xslt_profile is not None:
                self.log.debug('XSLT profiling results', extra={'_xslt_profile': xslt_profile.getroot()})

            if len(self.transform.error_log):
                self.log.warning(get_xsl_log())

            self.log.stage_tag('xsl')
            callback(xml_result)

        def exception_cb(exception):
            self.log.error('failed transformation with XSL %s', self.transform_filename)
            self.log.error(get_xsl_log())
            raise exception

        def get_xsl_log():
            xsl_line = 'XSLT {0.level_name} in file "{0.filename}", line {0.line}, column {0.column}\n\t{0.message}'
            return '\n'.join(map(xsl_line.format, self.transform.error_log))

        self.executor.add_job(job, self.handler.check_finished(success_cb), self.handler.check_finished(exception_cb))

    def _finish_with_xml(self, callback):
        self.log.debug('finishing without XSLT')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'application/xml; charset=utf-8')
        callback(self.doc.to_string())

    def xml_from_file(self, filename):
        return self.xml_cache.load(filename, self.log)

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)

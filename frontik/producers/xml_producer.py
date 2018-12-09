import copy
import os
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from lxml import etree
from tornado.concurrent import Future
from tornado.options import options

import frontik.doc
import frontik.util
from frontik import media_types
from frontik.producers import ProducerFactory
from frontik.util import get_abs_path
from frontik.xml_util import xml_from_file, xsl_from_file


class XMLProducerFactory(ProducerFactory):
    def __init__(self, application):
        xml_root = get_abs_path(application.app_root, options.xml_root)
        xsl_root = get_abs_path(application.app_root, options.xsl_root)

        @lru_cache(options.xml_cache_limit)
        def xml_from_file_cached(file):
            return xml_from_file(os.path.normpath(os.path.join(xml_root, file)))

        @lru_cache(options.xsl_cache_limit)
        def xsl_from_file_cached(file):
            return xsl_from_file(os.path.normpath(os.path.join(xsl_root, file)))

        self.xml_from_file_cached = xml_from_file_cached
        self.xsl_from_file_cached = xsl_from_file_cached

        self.executor = ThreadPoolExecutor(options.xsl_executor_pool_size)

    def get_producer(self, handler):
        return XmlProducer(handler, self.xml_from_file_cached, self.xsl_from_file_cached, self.executor)


class XmlProducer:
    def __init__(self, handler, xml_from_file_cached, xsl_from_file_cached, executor):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)
        self.executor = executor

        self.xml_from_file_cached = xml_from_file_cached
        self.xsl_from_file_cached = xsl_from_file_cached

        self.doc = frontik.doc.Doc()
        self.transform = None
        self.transform_filename = None

    def __call__(self):
        if any(frontik.util.get_cookie_or_url_param_value(self.handler, p) is not None for p in ('noxsl', 'notpl')):
            self.handler.require_debug_access()
            self.log.debug('ignoring XSLT because noxsl/notpl parameter is passed')
            return self._finish_with_xml()

        if not self.transform_filename:
            return self._finish_with_xml()

        try:
            self.transform = self.xsl_from_file_cached(self.transform_filename)
        except etree.XMLSyntaxError:
            self.log.error('failed parsing XSL file %s (XML syntax)', self.transform_filename)
            raise
        except etree.XSLTParseError:
            self.log.error('failed parsing XSL file %s (XSL parse error)', self.transform_filename)
            raise
        except Exception:
            self.log.error('failed loading XSL file %s', self.transform_filename)
            raise

        return self._finish_with_xslt()

    def set_xsl(self, filename):
        self.transform_filename = filename

    def _finish_with_xslt(self):
        self.log.debug('finishing with XSLT')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.TEXT_HTML)

        def job():
            start_time = time.time()
            result = self.transform(copy.deepcopy(self.doc.to_etree_element()),
                                    profile_run=self.handler.debug_mode.profile_xslt)
            return start_time, str(result), result.xslt_profile

        result_future = Future()

        def job_callback(future):
            if future.exception() is not None:
                self.log.error('failed transformation with XSL %s', self.transform_filename)
                self.log.error(get_xsl_log())

                result_future.set_exception(future.exception())
                return

            start_time, xml_result, xslt_profile = future.result()

            self.log.info('applied XSL %s in %.2fms', self.transform_filename, (time.time() - start_time) * 1000)

            if xslt_profile is not None:
                self.log.debug('XSLT profiling results', extra={'_xslt_profile': xslt_profile.getroot()})

            if len(self.transform.error_log):
                self.log.warning(get_xsl_log())

            self.handler.stages_logger.commit_stage('xsl')
            result_future.set_result(xml_result)

        def get_xsl_log():
            xsl_line = 'XSLT {0.level_name} in file "{0.filename}", line {0.line}, column {0.column}\n\t{0.message}'
            return '\n'.join(map(xsl_line.format, self.transform.error_log))

        render_future = self.executor.submit(job)
        self.handler.add_future(render_future, self.handler.check_finished(job_callback))
        return result_future

    def _finish_with_xml(self):
        self.log.debug('finishing without XSLT')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.APPLICATION_XML)

        future = Future()
        future.set_result(self.doc.to_string())
        return future

    def xml_from_file(self, filename):
        return copy.deepcopy(self.xml_from_file_cached(filename))

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)

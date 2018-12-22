import copy
import time
import weakref
from concurrent.futures import ThreadPoolExecutor

import tornado.ioloop
from lxml import etree
from tornado.options import options

import frontik.doc
import frontik.util
from frontik import file_cache
from frontik.producers import ProducerFactory
from frontik.util import get_abs_path, raise_future_exception
from frontik.xml_util import xml_from_file, xsl_from_file


class XMLProducerFactory(ProducerFactory):
    def __init__(self, application):
        self.xml_cache = file_cache.make_file_cache(
            'XML', 'xml_root',
            get_abs_path(application.app_root, options.xml_root),
            xml_from_file,
            options.xml_cache_limit,
            options.xml_cache_step,
            deepcopy=True
        )

        self.xsl_cache = file_cache.make_file_cache(
            'XSL', 'xsl_root',
            get_abs_path(application.app_root, options.xsl_root),
            xsl_from_file,
            options.xsl_cache_limit,
            options.xsl_cache_step
        )

        self.executor = ThreadPoolExecutor(options.xsl_executor_pool_size)

    def get_producer(self, handler):
        return XmlProducer(handler, xml_cache=self.xml_cache, xsl_cache=self.xsl_cache, executor=self.executor)


class XmlProducer:
    def __init__(self, handler, xml_cache=None, xsl_cache=None, executor=None):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)
        self.executor = executor
        self.ioloop = tornado.ioloop.IOLoop.current()

        self.xml_cache = xml_cache
        self.xsl_cache = xsl_cache

        self.doc = frontik.doc.Doc()
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
        except Exception:
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
                                    profile_run=self.handler.debug_mode.profile_xslt)
            return start_time, str(result), result.xslt_profile

        def job_callback(future):
            if future.exception() is not None:
                self.log.error('failed transformation with XSL %s', self.transform_filename)
                self.log.error(get_xsl_log())

                raise_future_exception(future)
                return

            start_time, xml_result, xslt_profile = future.result()

            self.log.info('applied XSL %s in %.2fms', self.transform_filename, (time.time() - start_time) * 1000)

            if xslt_profile is not None:
                self.log.debug('XSLT profiling results', extra={'_xslt_profile': xslt_profile.getroot()})

            if len(self.transform.error_log):
                self.log.warning(get_xsl_log())

            self.handler.stages_logger.commit_stage('xsl')
            callback(xml_result)

        def get_xsl_log():
            xsl_line = 'XSLT {0.level_name} in file "{0.filename}", line {0.line}, column {0.column}\n\t{0.message}'
            return '\n'.join(map(xsl_line.format, self.transform.error_log))

        future = self.executor.submit(job)
        self.ioloop.add_future(future, self.handler.check_finished(job_callback))
        return future

    def _finish_with_xml(self, callback):
        self.log.debug('finishing without XSLT')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'application/xml; charset=utf-8')
        callback(self.doc.to_string())

    def xml_from_file(self, filename):
        return self.xml_cache.load(filename, self.log)

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)

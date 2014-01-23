# coding=utf-8

import copy
import weakref
import time

from lxml import etree
import tornado.options

import frontik.doc
import frontik.handler
import frontik.jobs
import frontik.util


class XslProducer(object):
    def __init__(self, handler, xml_globals):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)

        if tornado.options.options.xsl_executor == 'threaded':
            self.executor = frontik.jobs.get_threadpool_executor()
        elif tornado.options.options.xsl_executor == 'ioloop':
            self.executor = frontik.jobs.IOLoopExecutor
        else:
            raise ValueError('Cannot initialize XslProducer with executor_type {0!r}'.format(
                tornado.options.options.executor_type))

        self.xml_cache = xml_globals.xml_cache
        self.xsl_cache = xml_globals.xsl_cache

        self.doc = frontik.doc.Doc(root_node=etree.Element('doc', frontik='true'))
        self.transform = None
        self.transform_filename = None

    def __call__(self, handler, callback):
        if frontik.util.get_cookie_or_url_param_value(self.handler, 'noxsl') is not None:
            self.handler.require_debug_access()
            self.log.debug('ignoring XSLT because noxsl parameter is passed')
            return self._finish_with_xml(callback)

        if not self.transform_filename:
            return self._finish_with_xml(callback)

        try:
            self.transform = self.xsl_cache.load(self.transform_filename, log=self.log)
        except etree.XMLSyntaxError:
            self.log.exception('failed parsing XSL file {0} (XML syntax)'.format(self.transform_filename))
            raise frontik.handler.HTTPError(500)
        except etree.XSLTParseError:
            self.log.exception('failed parsing XSL file {0} (XSL parse error)'.format(self.transform_filename))
            raise frontik.handler.HTTPError(500)
        except:
            self.log.exception('failed loading XSL file {0}'.format(self.transform_filename))
            raise frontik.handler.HTTPError(500)

        return self._finish_with_xslt(callback)

    def set_xsl(self, filename):
        self.transform_filename = filename

    def _finish_with_xslt(self, callback):
        self.log.debug('finishing with XSLT')

        if not self.handler._headers.get('Content-Type', None):
            self.handler.set_header('Content-Type', 'text/html')

        def job():
            start_time = time.time()
            result = self.transform(copy.deepcopy(self.doc.to_etree_element()),
                                    profile_run=self.handler.debug.debug_mode.profile_xslt)
            return start_time, str(result), result.xslt_profile

        def success_cb(result):
            start_time, xml_result, xslt_profile = result

            self.log.stage_tag('xsl')
            self.log.debug('applied XSL {0} in {1:.2f}ms'.format(
                self.transform_filename, (time.time() - start_time) * 1000))

            if xslt_profile is not None:
                self.log.debug('XSLT profiling results', extra={'_xslt_profile': xslt_profile.getroot()})
            if len(self.transform.error_log):
                self.log.info(get_xsl_log())

            callback(xml_result)

        def exception_cb(exception):
            self.log.error('failed transformation with XSL %s', self.transform_filename)
            self.log.error(get_xsl_log())
            raise exception

        def get_xsl_log():
            xsl_line = 'XSLT {0.level_name} in file "{0.filename}", line {0.line}, column {0.column}\n\t{0.message}'
            return '\n'.join(map(xsl_line.format, self.transform.error_log))

        self.executor.add_job(job, self.handler.async_callback(success_cb), self.handler.async_callback(exception_cb))

    def _finish_with_xml(self, callback):
        self.log.debug('finishing without XSLT')
        self.handler.set_header('Content-Type', 'application/xml')
        callback(self.doc.to_string())

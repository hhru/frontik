from __future__ import annotations

import contextvars
import copy
import re
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from lxml import etree
from tornado.ioloop import IOLoop

import frontik.doc
import frontik.util
from frontik import file_cache, media_types
from frontik.options import options
from frontik.producers import ProducerFactory
from frontik.util import get_abs_path
from frontik.xml_util import xml_from_file, xsl_from_file

if TYPE_CHECKING:
    from typing import Any

    from frontik.app import FrontikApplication
    from frontik.handler import PageHandler


class XmlProducer:
    METAINFO_PREFIX = 'hhmeta_'

    def __init__(
        self,
        handler: PageHandler,
        xml_cache: Any = None,
        xsl_cache: Any = None,
        executor: Any = None,
    ) -> None:
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)
        self.executor = executor

        self.xml_cache = xml_cache
        self.xsl_cache = xsl_cache

        self.doc = frontik.doc.Doc()
        self.transform: Any = None  # type: ignore
        self.transform_filename: str | None = None

    def __call__(self):
        if any(frontik.util.get_cookie_or_url_param_value(self.handler, p) is not None for p in ('noxsl', 'notpl')):
            self.handler.require_debug_access()
            self.log.debug('ignoring XSLT because noxsl/notpl parameter is passed')
            return self._finish_with_xml(escape_xmlns=True)

        if not self.transform_filename:
            return self._finish_with_xml()

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

        return self._finish_with_xslt()

    def set_xsl(self, filename: str) -> None:
        self.transform_filename = filename

    async def _finish_with_xslt(self) -> tuple[str | None, list[Any] | None]:
        self.log.debug('finishing with XSLT')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.TEXT_HTML)

        def job():
            start_time = time.time()
            result = self.transform(
                copy.deepcopy(self.doc.to_etree_element()),
                profile_run=self.handler.debug_mode.profile_xslt,
            )
            meta_info = [
                entry.message.replace(self.METAINFO_PREFIX, '')
                for entry in self.transform.error_log
                if entry.message.startswith(self.METAINFO_PREFIX)
            ]
            return start_time, (str(result), meta_info), result.xslt_profile

        def get_xsl_log() -> str:
            return '\n'.join(
                f'XSLT {e.level_name} in file "{e.filename}", line {e.line}, column {e.column}\n\t{e.message}'
                for e in self.transform.error_log
                if not e.message.startswith(self.METAINFO_PREFIX)
            )

        try:
            ctx = contextvars.copy_context()
            xslt_result = await IOLoop.current().run_in_executor(self.executor, lambda: ctx.run(job))
            if self.handler.is_finished():
                return None, None

            start_time, render_result, xslt_profile = xslt_result
            execution_time_ms = (time.time() - start_time) * 1000
            self.handler.statsd_client.time('xsl.time', int(execution_time_ms), xsl_file=self.transform_filename)

            self.log.info('applied XSL %s in %.2fms', self.transform_filename, execution_time_ms)

            if xslt_profile is not None:
                self.log.debug('XSLT profiling results', extra={'_xslt_profile': xslt_profile.getroot()})

            xsl_log = get_xsl_log()
            if xsl_log:
                self.log.warning(xsl_log)

            self.handler.stages_logger.commit_stage('xsl')
            return render_result

        except Exception as e:
            self.log.error('failed XSLT %s', self.transform_filename)
            self.log.error(get_xsl_log())
            raise e

    async def _finish_with_xml(self, escape_xmlns: bool = False) -> tuple[bytes, None]:
        self.log.debug('finishing without XSLT')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.APPLICATION_XML)

        if escape_xmlns:
            # https://support.google.com/chrome/thread/10921150?hl=en
            # когда хром при отображении xml натыкается на xmlns атрибут,
            # он пытается обрабатывать контент в соответствии с описанием атрибута.
            # Что в свою очередь ломает отображение xml документа (без плагинов)
            doc_string_without_xmlns = re.sub(
                'xmlns=".+?"',
                'xmlns-hidden="xmlns is hidden due to chrome xml viewer issues"',
                self.doc.to_string().decode('utf-8'),
            )
            return doc_string_without_xmlns.encode('utf-8'), None

        return self.doc.to_string(), None

    def xml_from_file(self, filename: str) -> Any:
        return self.xml_cache.load(filename, self.log)

    def __repr__(self):
        return f'{__package__}.{self.__class__.__name__}'


class XMLProducerFactory(ProducerFactory):
    def __init__(self, application: FrontikApplication) -> None:
        self.xml_cache = file_cache.make_file_cache(
            'XML',
            'xml_root',
            get_abs_path(application.app_root, options.xml_root),
            xml_from_file,
            options.xml_cache_limit,
            options.xml_cache_step,
            deepcopy=True,
        )

        self.xsl_cache = file_cache.make_file_cache(
            'XSL',
            'xsl_root',
            get_abs_path(application.app_root, options.xsl_root),
            xsl_from_file,
            options.xsl_cache_limit,
            options.xsl_cache_step,
        )

        self.executor = ThreadPoolExecutor(options.xsl_executor_pool_size)

    def get_producer(self, handler: PageHandler) -> XmlProducer:
        return XmlProducer(handler, xml_cache=self.xml_cache, xsl_cache=self.xsl_cache, executor=self.executor)

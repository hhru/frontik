# coding=utf-8

from lxml import etree

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        if self.get_argument('fail_early', None) is not None:
            self.add_early_postprocessor(Page._early_pp_1)
            self.add_early_postprocessor(Page._early_pp_2)

        self.set_xsl('postprocess.xsl')
        self.doc.put(etree.Element('node'))

        if self.get_argument('header', None) is not None:
            self.add_template_postprocessor(Page._header_pp)

        if self.get_argument('content', None) is not None:
            self.add_template_postprocessor(Page._content_pp)

        if self.get_argument('nocache', None) is not None:
            self.add_late_postprocessor(Page._nocache_pp)

        if self.get_argument('addserver', None) is not None:
            self.add_late_postprocessor(Page._addserver_pp)

    def _early_pp_1(self, callback):
        raise frontik.handler.HTTPError(400)

    def _early_pp_2(self, callback):
        raise frontik.handler.HTTPError(500)

    def _header_pp(self, tpl, callback):
        callback(tpl.replace('{{header}}', 'HEADER'))

    def _content_pp(self, tpl, callback):
        callback(tpl.replace('{{content}}', 'CONTENT'))

    def _nocache_pp(self, callback):
        self.set_header('Cache-Control', 'no-cache')
        callback()

    def _addserver_pp(self, callback):
        self.set_header('Server', 'Frontik')
        callback()

# coding=utf-8

import frontik.handler


class ContentPostprocessor(object):
    def __call__(self, handler, tpl, callback):
        callback(tpl.replace(b'%%content%%', b'CONTENT'))


class Page(frontik.handler.PageHandler):
    def get_page(self):
        if self.get_argument('fail_early', None) is not None:
            self.add_postprocessor(Page._early_pp_1)
            self.add_postprocessor(Page._early_pp_2)

        self.set_template('postprocess.html')
        self.json.put({'content': '%%content%%'})

        if self.get_argument('header', None) is not None:
            self.add_template_postprocessor(Page._header_pp)

        if self.get_argument('content', None) is not None:
            self.add_template_postprocessor(ContentPostprocessor())

    def _early_pp_1(self, callback):
        raise frontik.handler.HTTPError(400)

    def _early_pp_2(self, callback):
        raise frontik.handler.HTTPError(500)

    def _header_pp(self, tpl, callback):
        callback(tpl.replace(b'%%header%%', b'HEADER'))

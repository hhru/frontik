# coding=utf-8

from lxml import etree

from frontik.handler import FinishWithContent, HTTPError, PageHandler


class Page(PageHandler):
    def prepare(self):
        super(Page, self).prepare()

        def pp(handler, cb):
            handler.add_header('X-Foo', 'Bar')
            cb()

        self.add_early_postprocessor(pp)

    def get_page(self):
        content_type = self.get_argument('type', None)
        status_code = self.get_argument('code', None)

        def fail_page(_, __):
            raise HTTPError(500)

        self.post_url(self.request.host + self.request.path, callback=fail_page)

        if content_type == 'text':
            self.text = 'ok'
        elif content_type == 'json':
            self.json.put({'ok': True})
        elif content_type == 'xml':
            self.doc.put(etree.Element('ok'))

        if status_code is not None:
            raise FinishWithContent(int(status_code))

        raise FinishWithContent()

    def post_page(self):
        pass

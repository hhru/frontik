from lxml import etree
from tornado.web import HTTPError

from frontik.handler import FinishWithPostprocessors, PageHandler


class Page(PageHandler):
    def prepare(self):
        super().prepare()

        async def pp(handler):
            handler.add_header('X-Foo', 'Bar')

        self.add_postprocessor(pp)

    def get_page(self):
        content_type = self.get_argument('type')

        def fail_page(_, __):
            raise HTTPError(500)

        self.post_url(self.request.host, self.request.path, callback=fail_page)

        if content_type == 'text':
            self.text = 'ok'
        elif content_type == 'json':
            self.json.put({'ok': True})
        elif content_type == 'xml':
            self.doc.put(etree.Element('ok'))
        elif content_type == 'xsl':
            self.doc.put(etree.Element('ok'))
            self.set_xsl('simple.xsl')

        raise FinishWithPostprocessors()

    def post_page(self):
        pass

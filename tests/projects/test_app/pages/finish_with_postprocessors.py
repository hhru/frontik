from lxml import etree
from tornado.web import HTTPError

from frontik.handler import FinishWithPostprocessors, PageHandler, router


class Page(PageHandler):
    def prepare(self):
        super().prepare()

        def pp(handler):
            handler.add_header('X-Foo', 'Bar')

        self.add_postprocessor(pp)

    @router.get()
    async def get_page(self):
        content_type = self.get_argument('type')

        async def fail_request() -> None:
            await self.post_url(self.request.host, self.request.path)
            raise HTTPError(500)

        self.run_task(fail_request())

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

    @router.post()
    async def post_page(self):
        pass

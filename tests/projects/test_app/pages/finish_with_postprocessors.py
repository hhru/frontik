from lxml import etree
from tornado.web import HTTPError

from frontik.handler import FinishWithPostprocessors, PageHandler, get_current_handler
from frontik.routing import plain_router


class Page(PageHandler):
    def prepare(self):
        super().prepare()

        def pp(handler):
            handler.set_header('X-Foo', 'Bar')

        self.add_postprocessor(pp)


@plain_router.get('/finish_with_postprocessors', cls=Page)
async def get_page(handler=get_current_handler()):
    content_type = handler.get_query_argument('type')

    async def fail_request() -> None:
        await handler.post_url(handler.get_header('host'), handler.path)
        raise HTTPError(500)

    handler.run_task(fail_request())

    if content_type == 'text':
        handler.text = 'ok'
    elif content_type == 'json':
        handler.json.put({'ok': True})
    elif content_type == 'xml':
        handler.doc.put(etree.Element('ok'))
    elif content_type == 'xsl':
        handler.doc.put(etree.Element('ok'))
        handler.set_xsl('simple.xsl')

    raise FinishWithPostprocessors()


@plain_router.post('/finish_with_postprocessors', cls=Page)
async def post_page():
    pass

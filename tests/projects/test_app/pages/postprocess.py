from tornado.web import HTTPError

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


class ContentPostprocessor:
    def postprocessor(self, handler, tpl, meta_info):
        return tpl.replace('%%content%%', 'CONTENT')


class Page(PageHandler):
    @staticmethod
    def _pp_1(handler):
        raise HTTPError(400)

    @staticmethod
    def _pp_2(handler):
        handler.finish('FINISH_IN_PP')

    def _header_pp(self, tpl, meta_info):
        return tpl.replace('%%header%%', 'HEADER')


@router.get('/postprocess/', cls=Page)
async def get_page(handler: Page = get_current_handler()) -> None:
    if handler.get_query_argument('raise_error', None) is not None:
        handler.add_postprocessor(handler._pp_1)

    if handler.get_query_argument('finish', None) is not None:
        handler.add_postprocessor(handler._pp_2)

    if handler.get_query_argument('header', None) is not None:
        handler.add_render_postprocessor(Page._header_pp)

    if handler.get_query_argument('content', None) is not None:
        content_postprocessor = ContentPostprocessor()
        handler.add_render_postprocessor(content_postprocessor.postprocessor)

    handler.set_template('postprocess.html')
    handler.json.put({'content': '%%content%%'})

import asyncio

from tornado.web import HTTPError

from frontik.handler import PageHandler


class ContentPostprocessor:
    async def postprocessor(self, handler, tpl):
        await asyncio.sleep(0)
        return tpl.replace('%%content%%', 'CONTENT')


class Page(PageHandler):
    def get_page(self):
        if self.get_argument('raise_error', None) is not None:
            self.add_postprocessor(self._pp_1)

        if self.get_argument('finish', None) is not None:
            self.add_postprocessor(self._pp_2)

        if self.get_argument('header', None) is not None:
            self.add_render_postprocessor(Page._header_pp)

        if self.get_argument('content', None) is not None:
            content_postprocessor = ContentPostprocessor()
            self.add_render_postprocessor(content_postprocessor.postprocessor)

        self.set_template('postprocess.html')
        self.json.put({'content': '%%content%%'})

    @staticmethod
    async def _pp_1(handler):
        raise HTTPError(400)

    @staticmethod
    async def _pp_2(handler):
        handler.finish('FINISH_IN_PP')

    async def _header_pp(self, tpl):
        return tpl.replace('%%header%%', 'HEADER')

from tornado.web import Finish

from frontik.handler import PageHandler, router


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        throw = self.get_argument('throw', 'true') == 'true'
        code = int(self.get_argument('code', '200'))

        self.set_header('x-foo', 'Bar')
        self.set_status(code)

        if throw:
            msg = 'success'
            raise Finish(msg)
        else:
            self.finish('success')

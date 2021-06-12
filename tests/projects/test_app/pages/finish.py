from tornado.web import Finish

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        throw = self.get_argument('throw', 'true') == 'true'
        code = int(self.get_argument('code', '200'))

        self.set_header('x-foo', 'Bar')
        self.set_status(code)

        if throw:
            raise Finish('success')
        else:
            self.finish('success')

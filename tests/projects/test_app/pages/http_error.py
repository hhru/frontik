import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        throw_error = self.get_argument('throw', 'true') == 'true'
        code = int(self.get_argument('code', '200'))

        self.text = 'success'

        if throw_error:
            raise frontik.handler.HTTPError(code)
        else:
            self.set_status(code)

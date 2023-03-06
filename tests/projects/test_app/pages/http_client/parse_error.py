import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        el_result = await self.post_url(self.request.host, self.request.path + '?mode=xml')
        element = el_result.data
        if element is None:
            self.text = 'Parse error occured'
        else:
            assert False

        result = await self.post_url(self.request.host, self.request.path + '?mode=json')
        if result.failed:
            self.text = 'Parse error occured'
        else:
            assert False

    async def post_page(self):
        if self.get_argument('mode') == "xml":
            self.text = '''<doc frontik="tr"ue">this is broken xml</doc>'''
            self.set_header("Content-Type", "xml")
        elif self.get_argument('mode') == "json":
            self.text = '''{"hel"lo" : "this is broken json"}'''
            self.set_header("Content-Type", "json")

import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.set_template('empty.html')
        self.json.put({'x': 'y'})

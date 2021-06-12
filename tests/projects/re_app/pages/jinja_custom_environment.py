import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.set_template('jinja_custom_environment.html')
        self.json.put({})

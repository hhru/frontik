import frontik.handler


class Page(frontik.handler.AwaitablePageHandler):
    async def get_page(self):
        self.set_template('jinja_custom_environment.html')
        self.json.put({})

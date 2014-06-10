import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.json.put({
            'text': 'Hello, world!'
        })

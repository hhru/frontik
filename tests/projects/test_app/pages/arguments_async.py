import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.json.put({
            'тест': self.get_argument('param')
        })

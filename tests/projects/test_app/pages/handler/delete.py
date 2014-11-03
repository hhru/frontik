import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.json.put(
            self.delete_url(self.request.host + self.request.path, data={'data': 'true'})
        )

    def delete_page(self):
        self.json.put({
            'delete': self.get_argument('data')
        })

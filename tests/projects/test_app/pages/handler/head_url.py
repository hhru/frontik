import http.client

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        head_result = yield self.head_url(self.request.host, '/handler/head', name='head')

        if head_result.data == b'' and head_result.response.code == http.client.OK:
            self.text = 'OK'

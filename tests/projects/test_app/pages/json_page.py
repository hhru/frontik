# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self_uri = self.request.host + self.request.uri

        self.set_template('jinja.html')
        self.json.put({
            'req1': self.post_url(self_uri, data={'param': 1}),
            'req2': self.post_url(self_uri, data={'param': 2})
        })

    def post_page(self):
        self.json.put({
            'result': self.get_argument('param')
        })

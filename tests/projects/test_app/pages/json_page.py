# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self_uri = self.request.host + self.request.path
        invalid_json = self.get_argument('invalid', 'false')

        self.set_template('jinja.html')
        self.json.put({
            'req1': self.post_url(self_uri, data={'param': 1}),
            'req2': self.post_url(self_uri, data={'param': 2, 'invalid': invalid_json})
        })

    def post_page(self):
        invalid_json = self.get_argument('invalid', 'false') == 'true'

        if not invalid_json:
            self.json.put({
                'result': self.get_argument('param')
            })
        else:
            self.set_header('Content-Type', 'application/json')
            self.text = '{"result": FAIL}'

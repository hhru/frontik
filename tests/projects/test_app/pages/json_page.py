# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def prepare(self):
        if self.get_argument('custom_render', 'false') == 'true':
            def jinja_context_provider(handler):
                return {
                    'req1': {'result': 'custom1'},
                    'req2': {'result': 'custom2'},
                }

            self.jinja_context_provider = jinja_context_provider

        super(Page, self).prepare()

    def get_page(self):
        self_uri = self.request.host + self.request.path
        invalid_json = self.get_argument('invalid', 'false')

        data = {
            'req1': self.post_url(self_uri, data={'param': 1}),
            'req2': self.post_url(self_uri, data={'param': 2, 'invalid': invalid_json})
        }

        if self.get_argument('template_error', 'false') == 'true':
            del data['req1']

        self.set_template(self.get_argument('template', 'jinja.html'))
        self.json.put(data)

    def post_page(self):
        invalid_json = self.get_argument('invalid', 'false') == 'true'

        if not invalid_json:
            self.json.put({
                'result': self.get_argument('param')
            })
        else:
            self.set_header('Content-Type', 'application/json')
            self.text = '{"result": FAIL}'

# coding=utf-8

from frontik.handler import HTTPErrorWithPostprocessors
from frontik.micro_handler import MicroHandler
from frontik.preprocessors import preprocessor


@preprocessor
def get_page_preprocessor(handler):
    handler.json.put({
        'preprocessor': True
    })


class Page(MicroHandler):
    @get_page_preprocessor
    def get_page(self):
        fail_on_error = self.get_argument('fail_on_error', 'false') == 'true'

        if self.get_argument('return_none', 'false') == 'true':
            return

        return {
            'get': self.GET(self.request.host, self.request.path, data={'return_none': 'true'}, fail_on_error=True),
            'post': self.POST(self.request.host, self.request.path, data={'param': 'post'}),
            'put': self.PUT(self.request.host, self.request.path + '?code=401', fail_on_error=fail_on_error),
            'delete': self.DELETE(self.request.host, self.request.path, data={'invalid_dict_value': 'true'}),
        }

    def get_page_requests_failed(self, name, data, response):
        self.json.replace({'fail_on_error': True})
        raise HTTPErrorWithPostprocessors(403)

    def get_page_requests_done(self, results):
        assert results['post'].response.code == 200
        assert results['put'].response.code == 401
        assert results['delete'].response.code == 500

        self.json.put(results)

    def post_page(self):
        if self.get_argument('fail_on_error_default', 'false') == 'true':
            return {
                'e': self.PUT(
                    self.request.host, '{}?code={}'.format(self.request.path, self.get_argument('code')),
                    fail_on_error=True
                )
            }

        self.json.put({
            'POST': self.get_argument('param')
        })

    def post_page_requests_done(self, result):
        self.json.put(result)

    def put_page(self):
        # Testing parse_on_error=True
        self.json.put({'error': 'forbidden'})
        raise HTTPErrorWithPostprocessors(int(self.get_argument('code')))

    def delete_page(self):
        # Testing invalid return values
        if self.get_argument('invalid_dict_value', 'false') == 'true':
            return {'invalid': 'value'}
        elif self.get_argument('invalid_return_value', 'false') == 'true':
            return object()

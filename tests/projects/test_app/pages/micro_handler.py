from frontik.handler import HTTPError
from frontik.micro_handler import MicroHandler


def get_page(handler, callback):
    handler.json.put({
        'preprocessor': True
    })

    callback()


class Page(MicroHandler):
    @MicroHandler.add_preprocessor(get_page)
    @MicroHandler.add_preprocessor(get_page)
    def get_page(self):
        if self.get_argument('no-recursion', 'false') == 'true':
            return self.json.put({
                'GET': 'get'
            })

        fail_on_error = self.get_argument('fail_on_error', 'false') == 'true'

        return {
            'post': self.POST(self.request.host, self.request.path, data={'param': 'post'}),
            'put': self.PUT(self.request.host, self.request.path, fail_on_error=fail_on_error),
            'delete': self.DELETE(self.request.host, self.request.path + '?invalid_dict_value=true')
        }

    def get_page_requests_failed(self, name, data, response):
        if self.get_argument('default', 'false') != 'true':
            raise HTTPError(403, json={'fail_on_error': True})

    def get_page_requests_done(self, result):
        assert result['post'].response.code == 200
        assert result['put'].response.code == 401
        assert result['delete'].response.code == 500

        self.json.put(result)

    def post_page(self):
        self.json.put({
            'POST': self.get_argument('param')
        })

        return {
            'get': self.GET(self.request.host, self.request.uri, data={'no-recursion': 'true'})
        }

    def post_page_requests_done(self, result):
        self.json.put(result)

    def put_page(self):
        # Testing parse_on_error=True
        raise HTTPError(401, json={'error': 'forbidden'})

    def delete_page(self):
        if self.get_argument('invalid_dict_value', 'false') == 'true':
            return {'invalid': 'value'}
        elif self.get_argument('invalid_return_value', 'false') == 'true':
            return object()

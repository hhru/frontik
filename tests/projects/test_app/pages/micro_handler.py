from frontik.handler import HTTPError
from frontik.micro_handler import MicroHandler


class Page(MicroHandler):
    def get_page(self):
        if self.get_argument('no-recursion', 'false') == 'true':
            return self.json.put({
                'GET': 'get'
            })

        return {
            'get': Page.GET(self.request.host, self.request.uri, data={'no-recursion': 'true'}),
            'post': Page.POST(self.request.host, self.request.uri, data={'param': 'post'}),
            'put': Page.PUT(self.request.host, self.request.uri),
            'delete': Page.DELETE(self.request.host, self.request.uri)
        }

    def get_page_requests_done(self, result):
        assert result['get'].response.code == 200
        assert result['put'].response.code == 401

        self.json.put(result)

    def post_page(self):
        self.json.put({
            'POST': self.get_argument('param')
        })

    def post_page_requests_done(self, result):
        raise HTTPError(500, '*_page_requests_done method must not be called when there are no http calls')

    def put_page(self):
        # Testing parse_on_error=True
        raise HTTPError(401, json={'error': 'forbidden'})

    def delete_page(self):
        return {
            'invalid': 'behavior'
        }

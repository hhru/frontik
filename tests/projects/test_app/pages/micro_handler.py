# coding=utf-8

from tornado.concurrent import Future
from tornado.ioloop import IOLoop

from frontik.handler import HTTPError
from frontik.micro_handler import MicroHandler


def get_page(handler, callback):
    handler.json.put({
        'preprocessor': True
    })

    callback()


class Page(MicroHandler):
    @MicroHandler.add_preprocessor(get_page)
    def get_page(self):
        fail_on_error = self.get_argument('fail_on_error', 'false') == 'true'

        future_execution_time = float(self.get_argument('future_execution_time', 1.0))

        return {
            'post': self.POST(self.request.host, self.request.path, data={'param': 'post'}),
            'put': self.PUT(self.request.host, self.request.path + '?code=401', fail_on_error=fail_on_error),
            'delete': self.DELETE(self.request.host, self.request.path, data={'invalid_dict_value': 'true'}),
            'future': self.get_future_with_timeout('future_result', future_execution_time)
        }

    @staticmethod
    def get_page_requests_failed(name, data, response):
        raise HTTPError(403, json={'fail_on_error': True})

    def get_page_requests_done(self, results):
        assert results['post'].response.code == 200
        assert results['put'].response.code == 401
        assert results['delete'].response.code == 500
        assert results.get('future') is not None

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
        raise HTTPError(int(self.get_argument('code')), json={'error': 'forbidden'})

    def delete_page(self):
        if self.get_argument('invalid_dict_value', 'false') == 'true':
            return {'invalid': 'value'}
        elif self.get_argument('invalid_return_value', 'false') == 'true':
            return object()

    def get_future_with_timeout(self, result, delay):
        future = Future()

        def _finish_future():
            future.set_result(result)

        self.add_timeout(IOLoop.instance().time() + delay, _finish_future)
        return future

# coding=utf-8

import sys

from tornado.concurrent import Future, TracebackFuture
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
        fail_on_error_request = self.get_argument('fail_on_error_request', 'false') == 'true'
        fail_future = self.get_argument('fail_future', 'false') == 'true'

        if self.get_argument('return_none', 'false') == 'true':
            return

        return {
            'get': self.GET(self.request.host, self.request.path, data={'return_none': 'true'}),
            'post': self.POST(self.request.host, self.request.path, data={'param': 'post'}),
            'put': self.PUT(self.request.host, self.request.path + '?code=401', fail_on_error=fail_on_error_request),
            'delete': self.DELETE(self.request.host, self.request.path, data={'invalid_dict_value': 'true'}),
            'future': self.get_future('future_result', exception=fail_future)
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
        # Testing invalid return values
        if self.get_argument('invalid_dict_value', 'false') == 'true':
            return {'invalid': 'value'}
        elif self.get_argument('invalid_return_value', 'false') == 'true':
            return object()

    def get_future(self, result, exception=False):
        future = Future()

        def _finish_future():
            if exception:
                future.set_exception(ValueError('Some error'))
            else:
                future.set_result(result)

        self.add_timeout(IOLoop.current().time() + 0.5, _finish_future)
        return future

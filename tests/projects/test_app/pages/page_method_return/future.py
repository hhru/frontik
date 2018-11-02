# coding=utf-8

from tornado.concurrent import Future
from tornado.ioloop import IOLoop

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        fail_on_error_future = self.get_argument('fail_on_error_future', 'false') == 'true'
        fail_future = self.get_argument('fail_future', 'false') == 'true'

        return {
            'future': self.get_future('future_result', exception=fail_future, fail_on_error=fail_on_error_future)
        }

    def get_page_requests_done(self, results):
        self.json.put(results)

    def get_future(self, result, exception=False, fail_on_error=False):
        future = Future()
        future.fail_on_error = fail_on_error

        def _finish_future():
            if exception:
                future.set_exception(ValueError('Some error'))
            else:
                future.set_result(result)

        self.add_timeout(IOLoop.current().time() + 0.5, _finish_future)
        return future

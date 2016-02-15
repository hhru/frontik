# coding=utf-8

from tornado.concurrent import Future

import frontik.handler
from frontik.http_client import FailedRequestException


class Page(frontik.handler.PageHandler):
    def get_page(self):
        future = Future()

        if self.get_argument('failed_future', 'false') == 'true':
            future.set_exception(FailedRequestException(reason='error', code='code'))
        else:
            future.set_result({'1': 'yay'})

        another_future = Future()
        another_future.set_result({'2': 'yay'})

        def _final_callback(results):
            self.json.put({'final_callback_called': True})

        self.json.put(
            self.group(
                {
                    '1': future,
                    '2': another_future,
                },
                _final_callback,
                name='test async'
            )
        )

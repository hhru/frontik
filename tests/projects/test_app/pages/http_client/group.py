# coding=utf-8
from tornado.concurrent import Future

import frontik.handler
from frontik.http_client import FailedRequestException


class Page(frontik.handler.PageHandler):
    def get_page(self):
        url = self.request.host + self.request.path

        future = Future()

        if self.get_argument('failed_future', 'false') == 'true':
            future.set_exception(FailedRequestException(reason='error', code='code'))
        else:
            future.set_result({'1': 'yay'})

        another_future = Future()
        another_future.set_result({'2': 'yay'})

        def _final_callback(results):
            self.json.put({'final_callback_called': True})

        def _callback(json, response):
            if self.get_argument('fail', 'false') == 'true':
                raise Exception('I''m dying!')

        group = {
            '1': future,
            '2': another_future,
        }

        if self.get_argument('only_resolved_futures', 'false') == 'false':
            group.update({
                '3': self.post_url(url + '?data=3', callback=_callback),
                '4': self.post_url(url + '?data=4'),
            })

        self.json.put(
            self.group(group, _final_callback, name='test async')
        )

    def post_page(self):
        self.json.put({
            self.get_argument('data'): 'yay'
        })

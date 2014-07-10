# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        ensure_callback_is_async = False
        url = self.request.host + self.request.path
        fail = self.get_argument('fail', 'false') == 'true'

        def _async_callback(results):
            """Assert that callback is executed asynchronously"""
            assert ensure_callback_is_async

        def _final_callback(results):
            assert results['1'].data == {'1': 'yay'}
            assert results['2'].data == {'2': 'yay'}
            assert results['3'].data is None
            assert results['3'].response.error

        def _maybe_failing_callback(text, response):
            if fail:
                raise Exception('I''m dying!')

        self.json.put(
            self.group(
                {
                    '1': self.post_url(url + '?data=1'),
                    '2': self.post_url(url + '?data=2', callback=_maybe_failing_callback),
                    '3': self.post_url(url)
                },
                _final_callback,
                name='test async'
            )
        )

        self.group({}, _async_callback)
        ensure_callback_is_async = True

    def post_page(self):
        self.json.put({
            self.get_argument('data'): 'yay'
        })

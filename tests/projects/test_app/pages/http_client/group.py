# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        url = self.request.host + self.request.path

        def _final_callback(results):
            self.json.put({'final_callback_called': True})

        def _callback(json, response):
            if self.get_argument('fail', 'false') == 'true':
                raise Exception('I''m dying!')

        self.json.put(
            self.group(
                {
                    '1': self.post_url(url + '?data=1'),
                    '2': self.post_url(url + '?data=2', callback=_callback)
                },
                _final_callback,
                name='test async'
            )
        )

    def post_page(self):
        self.json.put({
            self.get_argument('data'): 'yay'
        })

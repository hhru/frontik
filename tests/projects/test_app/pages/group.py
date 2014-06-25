# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        url = self.request.host + self.request.path

        def _final_callback(results):
            pass

        def _failing_callback(text, response):
            raise Exception('I''m dying!')

        self.json.put(
            self.group(
                {
                    '1': self.post_url(url + '?data=1', callback=_failing_callback),
                },
                _final_callback,
                name='test async'
            )
        )

    def post_page(self):
        self.json.put({
            self.get_argument('data'): 'yay'
        })

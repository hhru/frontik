# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        state = {
            'marker_second_callback_is_sync': False,
        }
        url = self.request.host + self.request.path

        def main_callback(json, response):
            self.json.put(json)

        def second_additional_callback(future):
            state['marker_second_callback_is_sync'] = True

        def additional_callback(future):
            self.json.put({'cb': 'yes'})
            request_future.add_done_callback(second_additional_callback)
            assert state['marker_second_callback_is_sync']

            self.json.put(self.post_url(url + '?data=2'))

        request_future = self.post_url(url + '?data=1', callback=main_callback)
        request_future.add_done_callback(additional_callback)

    def post_page(self):
        self.json.put({
            self.get_argument('data'): 'yay'
        })

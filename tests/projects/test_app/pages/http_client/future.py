# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        state = {
            'second_callback_must_be_synchronous': False,
        }

        def main_callback(json, response):
            self.json.put({
                'main_callback_called': True
            })

        def second_additional_callback(future):
            state['marker_second_callback_is_sync'] = True

        def additional_callback(future):
            assert future is request_future

            self.json.put({
                'additional_callback_called': True
            })

            request_future.add_done_callback(second_additional_callback)
            assert state['second_callback_must_be_synchronous']

        request_future = self.post_url(self.request.host + self.request.path, callback=main_callback)
        request_future.add_done_callback(additional_callback)

    def post_page(self):
        self.json.put({
            'yay': 'yay'
        })

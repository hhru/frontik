import frontik.handler
from frontik.util import gather_dict


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        ensure_callback_is_async = False
        fail_callback = self.get_argument('fail_callback', 'false') == 'true'
        fail_request = self.get_argument('fail_request', 'false') == 'true'

        async def _async_callback():
            """Assert that callback is executed asynchronously"""
            assert ensure_callback_is_async

        def _future_callback(future):
            self.json.put({'future_callback_result': future.result()['4'].data['4']})

        async def put_json_data():
            result = await gather_dict({
                '1': self.post_url(self.request.host, self.request.path + '?data=1'),
                '2': self.post_url(self.request.host, self.request.path + '?data=2'),
                '3': self.post_url(self.request.host, self.request.path,
                                   data={'data': '3' if not fail_request else None}, parse_on_error=False)
            })
            if fail_callback:
                raise Exception("I'm dying!")

            self.json.put({'final_callback_called': True})
            self.json.put(result)

        self.run_task(put_json_data())

        self.run_task(_async_callback())
        ensure_callback_is_async = True

        future = self.group({
            '4': self.post_url(self.request.host, self.request.path + '?data=4')
        })
        self.add_future(future, self.finish_group.add(_future_callback))

    async def post_page(self):
        self.json.put({
            self.get_argument('data'): 'yay'
        })

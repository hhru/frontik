from tornado.concurrent import Future

import frontik.handler


class Page(frontik.handler.AwaitablePageHandler):
    async def get_page(self):
        future = Future()

        if self.get_argument('failed_future', 'false') == 'true':
            future.set_exception(Exception('failed future exception'))
        else:
            future.set_result({'1': 'yay'})

        another_future = Future()
        another_future.set_result({'2': 'yay'})

        self.json.put(
            self.group(
                {
                    '1': future,
                    '2': another_future,
                }
            )
        )

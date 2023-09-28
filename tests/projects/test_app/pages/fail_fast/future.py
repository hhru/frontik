from tornado.concurrent import Future
from tornado.ioloop import IOLoop

from frontik.handler import PageHandler
from frontik.util import gather_dict


class Page(PageHandler):
    async def get_page(self):
        fail_future = self.get_argument('fail_future', 'false') == 'true'

        results = await gather_dict({'future': self.get_future('future_result', exception=fail_future)})

        self.json.put(results)

    def get_future(self, result: str, exception: bool=False) -> Future:
        future: Future = Future()

        def _finish_future():
            if exception:
                future.set_exception(ValueError('Some error'))
            else:
                future.set_result(result)

        self.add_timeout(IOLoop.current().time() + 0.3, _finish_future)
        return future

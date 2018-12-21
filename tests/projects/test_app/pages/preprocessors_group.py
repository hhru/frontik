import time

from tornado import gen
from tornado.concurrent import Future

from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor


def waiting_preprocessor(sleep_time_sec, preprocessor_name, add_to_preprocessors_group):
    @preprocessor
    def pp(handler):
        def _put_to_completed():
            handler.completed_preprocessors = getattr(handler, 'completed_preprocessors', [])
            handler.completed_preprocessors.append(preprocessor_name)
            wait_future.set_result(preprocessor_name)

        wait_future = Future()
        handler.add_timeout(time.time() + sleep_time_sec, _put_to_completed)

        if add_to_preprocessors_group:
            handler.add_to_preprocessors_group(wait_future)

    return pp


@preprocessor
def pp_1(handler):
    future = Future()
    handler.add_to_preprocessors_group(future)
    future.set_result(None)
    yield gen.sleep(0.1)  # give time for future callbacks to complete


class Page(PageHandler):

    @waiting_preprocessor(0.7, "should_finish_after_page_finish", False)
    @waiting_preprocessor(0.5, "should_finish_third", True)
    @waiting_preprocessor(0.1, "should_finish_first", False)
    @waiting_preprocessor(0.3, "should_finish_second", True)
    @waiting_preprocessor(0.9, "should_finish_after_page_finish", False)
    def get_page(self):
        assert hasattr(self, 'completed_preprocessors')
        self.json.put({'preprocessors': self.completed_preprocessors})

    @pp_1
    @pp_1  # preprocessors_group must not finish until all preprocessors are completed
    def post_page(self):
        pass

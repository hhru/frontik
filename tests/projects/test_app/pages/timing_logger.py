from frontik.handler import PageHandler
from frontik.loggers.timings import TimingsLoggerFactory


class Page(PageHandler):
    def get_page(self):
        factory = TimingsLoggerFactory(self, lambda handler: {'param1': handler.param1})
        timings_logger = factory.create_logger('metric_name')

        self.param1 = 1
        timings_logger.commit_time(param2='param2')

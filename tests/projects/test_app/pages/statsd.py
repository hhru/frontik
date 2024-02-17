from frontik.handler import PageHandler, router


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        self.statsd_client.count('count_metric', 10, tag1='tag1', tag2='tag2')
        self.statsd_client.gauge('gauge_metric', 100, tag='tag3')
        self.statsd_client.time('time_metric', 1000, tag='tag4')

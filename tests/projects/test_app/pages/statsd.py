from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/statsd', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.statsd_client.count('count_metric', 10, tag1='tag1', tag2='tag2')
    handler.statsd_client.gauge('gauge_metric', 100, tag='tag3')
    handler.statsd_client.time('time_metric', 1000, tag='tag4')

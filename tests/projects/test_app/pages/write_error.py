from frontik.handler import PageHandler
from frontik.routing import plain_router


class Page(PageHandler):
    def write_error(self, status_code=500, **kwargs):
        self.json.put({'write_error': True})

        if self.get_argument('fail_write_error', 'false') == 'true':
            raise Exception('exception in write_error')

        self.finish_with_postprocessors()


@plain_router.get('/write_error', cls=Page)
async def get_page():
    raise Exception('exception in handler')

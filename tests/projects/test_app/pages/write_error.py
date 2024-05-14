from frontik.handler import PageHandler
from frontik.routing import router


class Page(PageHandler):
    async def write_error(self, status_code=500, **kwargs):
        self.set_status(status_code)
        self.json.put({'write_error': True})

        if self.get_query_argument('fail_write_error', 'false') == 'true':
            raise Exception('exception in write_error')

        return await self.finish_with_postprocessors()


@router.get('/write_error', cls=Page)
async def get_page():
    raise Exception('exception in handler')

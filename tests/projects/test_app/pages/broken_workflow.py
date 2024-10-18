from tornado.web import HTTPError

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from frontik.util import gather_list


@router.get('/broken_workflow', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    port = int(handler.get_query_argument('port'))

    @handler.check_finished
    def cb(*args, **kw):
        raise HTTPError(400)

    results = await gather_list(
        handler.get_url(f'http://localhost:{port}', '/page/simple/'),
        handler.get_url(f'http://localhost:{port}', '/page/simple/'),
        handler.get_url(f'http://localhost:{port}', '/page/simple/'),
    )
    for res in results:
        cb(res)

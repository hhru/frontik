from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/sentry_not_configured', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    assert not hasattr(handler, 'get_sentry_logger')

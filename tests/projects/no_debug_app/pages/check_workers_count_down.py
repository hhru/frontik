from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/check_workers_count_down', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.text = str(handler.application.worker_state.init_workers_count_down.value)

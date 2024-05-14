import logging

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router

custom_logger = logging.getLogger('custom_logger')


@router.get('/log', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.log.debug('debug')
    handler.log.info('info')

    try:
        msg = 'test'
        raise Exception(msg)
    except Exception:
        handler.log.exception('exception')
        handler.log.error('error', stack_info=True)

    handler.log.critical('critical')

    custom_logger.fatal('fatal')

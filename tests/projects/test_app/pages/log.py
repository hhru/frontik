import logging

from frontik.routing import router

handler_logger = logging.getLogger('handler')
custom_logger = logging.getLogger('custom_logger')


@router.get('/log')
async def get_page():
    handler_logger.debug('debug')
    handler_logger.info('info')

    try:
        raise Exception('test')
    except Exception:
        handler_logger.exception('exception')
        handler_logger.error('error', stack_info=True)

    handler_logger.critical('critical')

    custom_logger.fatal('fatal')

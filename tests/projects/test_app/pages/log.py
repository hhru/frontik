import logging

import frontik.handler
from frontik.handler import router

custom_logger = logging.getLogger('custom_logger')


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.log.debug('debug')
        self.log.info('info')

        try:
            msg = 'test'
            raise Exception(msg)
        except Exception:
            self.log.exception('exception')
            self.log.error('error', stack_info=True)

        self.log.critical('critical')

        custom_logger.fatal('fatal')

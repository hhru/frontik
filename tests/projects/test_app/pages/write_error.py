# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        raise Exception('exception in handler')

    def write_error(self, status_code=500, **kwargs):
        self.json.put({'write_error': True})

        if self.get_argument('fail_write_error', 'false') == 'true':
            raise Exception('exception in write_error')

        self.finish_with_postprocessors()

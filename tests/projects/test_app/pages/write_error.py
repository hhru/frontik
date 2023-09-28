import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        msg = 'exception in handler'
        raise Exception(msg)

    def write_error(self, status_code=500, **kwargs):
        self.json.put({'write_error': True})

        if self.get_argument('fail_write_error', 'false') == 'true':
            msg = 'exception in write_error'
            raise Exception(msg)

        self.finish_with_postprocessors()

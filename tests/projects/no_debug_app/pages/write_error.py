import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        pass

    def write_error(self, status_code=500, **kwargs):
        exception = kwargs['exc_info'][1] if 'exc_info' in kwargs else None
        if isinstance(exception, frontik.handler.DebugUnauthorizedHTTPError):
            self.finish('DebugUnauthorizedHTTPError')

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self) -> dict:
        return {'str_field': 'Привет'}

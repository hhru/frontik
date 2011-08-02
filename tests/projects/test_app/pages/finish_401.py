import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        raise frontik.handler.HTTPError(401, headers={'WWW-Authenticate': 'Basic realm="Secure Area"'})

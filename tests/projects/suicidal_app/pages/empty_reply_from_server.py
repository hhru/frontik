import sys

import frontik.handler


class Page(frontik.handler.PageHandler):
    def post_page(self):
        sys.exit()

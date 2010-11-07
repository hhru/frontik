import frontik.handler
import frontik.auth

class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.require_debug_access('user', 'god')
        self.doc.put('authenticated!')

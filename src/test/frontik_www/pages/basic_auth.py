import frontik.handler
import frontik.auth

class Page(frontik.handler.PageHandler):
    def get_page(self):
        frontik.auth.require_basic_auth(self, 'user', 'god')
        self.doc.put('authenticated!')

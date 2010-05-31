import frontik.handler
import frontik.basic_auth

class Page(frontik.handler.PageHandler):
    @frontik.basic_auth.require_basic_auth('user', 'god')
    def get_page(self):
        self.doc.put('authenticated!')
import frontik.handler

frontik_import('lib')

class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.doc.put(lib.a)

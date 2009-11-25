import frontik

class Page(frontik.PageHandler):
    def get(self):
        self.doc.put('hello world!')
        self.finish_page()

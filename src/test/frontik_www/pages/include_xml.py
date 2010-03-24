import frontik.handler

class Page(frontik.handler.PageHandler):
    def get(self):
        self.doc.put(self.xml_from_file('aaa.xml'))
        self.finish_page()

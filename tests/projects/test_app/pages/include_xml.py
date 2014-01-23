import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.doc.put(self.xml_from_file('aaa.xml'))

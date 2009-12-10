import frontik.handler
from frontik import etree

class Page(frontik.handler.PageHandler):
    def get(self):
        self.doc.put(etree.Element('ok'))

        self.finish_page()

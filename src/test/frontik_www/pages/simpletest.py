import frontik
from frontik import etree

class Page(frontik.PageHandler):
    def get(self):
        self.doc.put(etree.Element('ok'))
        self.finish_page()

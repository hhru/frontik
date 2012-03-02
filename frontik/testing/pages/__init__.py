import frontik.handler
from lxml import etree
class Page(frontik.handler.PageHandler):

    def get_page(self):
        hello = etree.Element('hello')
        hello.text = 'Hello testing!'
        self.doc.put(hello)

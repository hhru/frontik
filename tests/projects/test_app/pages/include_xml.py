import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.doc.put(self.xml_from_file('aaa.xml'))

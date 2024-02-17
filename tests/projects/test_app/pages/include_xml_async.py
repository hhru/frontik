import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.doc.put(self.xml_from_file('aaa.xml'))

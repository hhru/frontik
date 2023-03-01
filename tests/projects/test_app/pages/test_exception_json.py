from frontik.handler import HTTPErrorWithPostprocessors, PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.json.put({'reason': 'bad argument'})
        raise HTTPErrorWithPostprocessors(400)

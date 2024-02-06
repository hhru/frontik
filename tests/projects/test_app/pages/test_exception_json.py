from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, router


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        self.json.put({'reason': 'bad argument'})
        raise HTTPErrorWithPostprocessors(400)

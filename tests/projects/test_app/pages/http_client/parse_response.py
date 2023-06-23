from tornado.escape import to_unicode

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler


class Page(PageHandler):
    async def get_page(self):
        result = await self.post_url(self.request.host, self.request.path, parse_on_error=True)
        self.json.put(result.data)
        result = await self.put_url(self.request.host, self.request.path, parse_on_error=False)
        self.json.put(result.to_dict())  # TODO т.е. у нас failed, и data_parse_error и мы хотим этот ерор докпутнуть? реально?

        result = await self.delete_url(self.request.host, self.request.path, parse_response=False)
        if not result.failed:
            self.json.put({'delete': to_unicode(result.data)})

    async def post_page(self):
        self.json.put({'post': True})
        raise HTTPErrorWithPostprocessors(400)

    async def put_page(self):
        self.json.put({'put': True})
        raise HTTPErrorWithPostprocessors(400)

    async def delete_page(self):
        self.text = 'deleted'

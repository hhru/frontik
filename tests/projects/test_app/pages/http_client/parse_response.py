from tornado.escape import to_unicode
from frontik.handler import router
from frontik.handler import HTTPErrorWithPostprocessors, PageHandler


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        result = await self.post_url(self.request.host, self.request.path, parse_on_error=True)
        self.json.put(result.data)
        result = await self.put_url(self.request.host, self.request.path, parse_on_error=False)
        self.json.put(result.to_dict())

        result = await self.delete_url(self.request.host, self.request.path, parse_response=False)
        if not result.failed:
            self.json.put({'delete': to_unicode(result.data)})

    @router.post()
    async def post_page(self):
        self.json.put({'post': True})
        raise HTTPErrorWithPostprocessors(400)

    @router.put()
    async def put_page(self):
        self.json.put({'put': True})
        raise HTTPErrorWithPostprocessors(400)

    @router.delete()
    async def delete_page(self):
        self.text = 'deleted'

import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.set_template('jinja_custom_environment.html')
        self.json.put({})

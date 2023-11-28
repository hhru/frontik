import frontik.handler

response = {
    **{f"10{i}": i for i in range(5)},
    **{f"20{i}": [i, i, i] for i in range(5)},
    **{f"30{i}": {str(i): i} for i in range(5)},
}


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.json.put(response)

    async def post_page(self):
        self.json.put(response)

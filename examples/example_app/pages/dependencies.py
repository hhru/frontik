
from frontik.dependency_manager import dependency
from frontik.handler import PageHandler
from frontik.options import options


# response = {
#     **{f"10{i}": i for i in range(5)},
#     **{f"20{i}": [i, i, i] for i in range(5)},
#     **{f"30{i}": {str(i): i} for i in range(5)},
# }


async def dep0(handler: PageHandler):
    handler.json.put({"a1": "b"})


async def dep1(handler: PageHandler, d0=dependency(dep0)):
    # await handler.get_url(f'127.0.0.1:{options.port}', '/handler_with_large_json_body', fail_fast=True)
    handler.json.put({"a1": "b"})


async def dep3(handler: PageHandler):
    handler.json.put({"a3": "b"})


async def dep2(handler: PageHandler, d3=dependency(dep3)):
    # await handler.get_url(f'127.0.0.1:{options.port}', '/handler_with_large_json_body', fail_fast=True)
    handler.json.put({"a2": "b"})


class Page(PageHandler):
    async def get_page(self, d1=dependency(dep1), d2=dependency(dep2)):
        pass

    async def post_page(self):
        pass

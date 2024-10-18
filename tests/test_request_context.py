# Были какие-то тесты на то, что контекст не теряется при всяких пэйджовых штуках типа финиш групп, корутин и прочего
# перенести в фпх

# import asyncio
# from concurrent.futures import ThreadPoolExecutor
# from functools import partial
# from typing import Any
#
# from fastapi import Request
#
# from frontik import request_context
# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import router
#
#
# async def _callback(name: str, handler: PageHandler) -> None:
#     handler.json.put({name: request_context.get_handler_name()})
#
#
# class Page(PageHandler):
#     async def run_coroutine(self, host: str) -> None:
#         self.json.put({'coroutine_before_yield': request_context.get_handler_name()})
#
#         await self.post_url(host, self.path)
#
#         self.json.put({'coroutine_after_yield': request_context.get_handler_name()})
#
#     def __repr__(self):
#         return 'request_context'
#
#
# @router.get('/request_context', cls=Page)
# async def get_page(request: Request, handler: Page = get_current_handler()) -> None:
#     def _waited_callback(name: str, _task: Any) -> None:
#         task = asyncio.create_task(_callback(name, handler))
#         handler.finish_group.add_future(task)
#
#     handler.json.put({'page': request_context.get_handler_name()})
#
#     dumb_task = asyncio.create_task(asyncio.sleep(0))
#     dumb_task.add_done_callback(partial(_waited_callback, 'callback'))
#     await dumb_task
#
#     ThreadPoolExecutor(1).submit(_waited_callback, 'executor', None)
#
#     handler.run_task(handler.run_coroutine(request.headers.get('host', '')))
#
#     async def make_request() -> None:
#         await handler.post_url(request.headers.get('host', ''), handler.path)
#
#     future = asyncio.create_task(make_request())
#     future.add_done_callback(partial(_waited_callback, 'future'))
#
#
# @router.post('/request_context', cls=Page)
# async def post_page():
#     pass


# class TestRequestContext:
#     def test_request_context(self):
#         json = frontik_test_app.get_page_json('request_context')
#
#         controller = 'tests.projects.test_app.pages.request_context.get_page'
#
#         assert json == {
#             'page': controller,
#             'callback': controller,
#             'coroutine_before_yield': controller,
#             'coroutine_after_yield': controller,
#         }


from frontik import request_context
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/request_context')
async def get_page():
    return request_context.get_handler_name()


class TestRequestContext(FrontikTestBase):
    async def test_request_context(self):
        response = await self.fetch('/request_context')
        controller = 'tests.test_request_context.get_page'
        assert response.data == controller

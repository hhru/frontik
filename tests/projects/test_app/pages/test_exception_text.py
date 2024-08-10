from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, get_current_handler
from frontik.routing import plain_router
from frontik.util import gather_list


@plain_router.get('/test_exception_text', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    async def bad_post_requests() -> None:
        results = await gather_list(
            handler.post_url(handler.get_header('host'), handler.path),
            handler.post_url(handler.get_header('host'), handler.path),
            handler.post_url(handler.get_header('host'), handler.path),
            handler.post_url(handler.get_header('host'), handler.path),
        )
        for _ in results:
            raise AssertionError()

    handler.run_task(bad_post_requests())

    handler.text = 'This is just a plain text'
    raise HTTPErrorWithPostprocessors(403)

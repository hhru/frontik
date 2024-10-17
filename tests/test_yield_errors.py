#какая-то дичь

# error_yield.py

# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import plain_router
#
#
# @plain_router.get('/error_yield', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     await handler.post_url(handler.get_header('host'), handler.path)
#     return 1 / 0
#
#
# @plain_router.post('/error_yield', cls=PageHandler)
# async def post_page(handler=get_current_handler()):
#     handler.text = 'result'


#from tests.instances import frontik_test_app


# class TestHandler:
#     def test_error_in_yield(self) -> None:
#         response = frontik_test_app.get_page('/error_yield')
#         assert response.status_code == 500

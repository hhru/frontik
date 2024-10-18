# чисто тестинг методов пэйдж хэндлера, едет в фпх

# test_app/pages/mandatory_headers.py

# from tornado.web import HTTPError
#
# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import router
#
#
# @router.get('/mandatory_headers', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     if handler.get_argument('test_mandatory_headers', None) is not None:
#         handler.set_mandatory_header('TEST_HEADER', 'TEST_HEADER_VALUE')
#         handler.set_mandatory_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
#         raise HTTPError(500)
#
#     elif handler.get_argument('test_without_mandatory_headers', None) is not None:
#         handler.add_header('TEST_HEADER', 'TEST_HEADER_VALUE')
#         handler.set_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
#         raise HTTPError(500)
#
#     elif handler.get_argument('test_clear_set_mandatory_headers', None) is not None:
#         handler.set_mandatory_header('TEST_HEADER', 'TEST_HEADER_VALUE')
#         handler.set_mandatory_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
#         handler.clear_header('TEST_HEADER')
#         handler.clear_cookie('TEST_COOKIE')
#         raise HTTPError(500)
#
#     elif handler.get_argument('test_clear_not_set_headers', None) is not None:
#         handler.clear_header('TEST_HEADER')
#         handler.clear_cookie('TEST_COOKIE')
#         raise HTTPError(500)
#
#     elif handler.get_argument('test_invalid_mandatory_cookie') is not None:
#         handler.set_mandatory_cookie('TEST_COOKIE', '<!--#include file="/etc/passwd"-->')
#         raise HTTPError(500)

# from tests.instances import frontik_test_app
#
#
# class TestPostprocessors:
#     def test_set_mandatory_headers(self):
#         response = frontik_test_app.get_page('mandatory_headers?test_mandatory_headers')
#         assert response.status_code == 500
#         assert response.headers.get('TEST_HEADER') == 'TEST_HEADER_VALUE'
#         assert response.cookies.get('TEST_COOKIE') == 'TEST_HEADER_COOKIE'  # type: ignore
#
#     def test_mandatory_headers_are_lost(self) -> None:
#         response = frontik_test_app.get_page('mandatory_headers?test_without_mandatory_headers')
#         assert response.status_code == 500
#         assert response.headers.get('TEST_HEADER') is None
#         assert response.headers.get('TEST_COOKIE') is None
#
#     def test_mandatory_headers_are_cleared(self) -> None:
#         response = frontik_test_app.get_page('mandatory_headers?test_clear_set_mandatory_headers')
#         assert response.status_code == 500
#         assert response.headers.get('TEST_HEADER') is None
#         assert response.headers.get('TEST_COOKIE') is None
#
#     def test_clear_not_set_headers_does_not_faile(self) -> None:
#         response = frontik_test_app.get_page('mandatory_headers?test_clear_not_set_headers')
#         assert response.status_code == 500
#         assert response.headers.get('TEST_HEADER') is None
#         assert response.headers.get('TEST_COOKIE') is None
#
#     def test_invalid_mandatory_cookie(self):
#         response = frontik_test_app.get_page('mandatory_headers?test_invalid_mandatory_cookie')
#         assert response.status_code == 400
#         assert response.headers.get('TEST_COOKIE') is None

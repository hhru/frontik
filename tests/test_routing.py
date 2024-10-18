# какая-то херня вроде должен роутинг теститься, а проверяются всякик xml
# оставил тесты регэксп роутинга (фастапишный нет смысла тестить) и 404.
# Остальное если надо можно перенести в фпх или удалить
from fastapi import Request
from frontik.routing import router, regex_router
from frontik.testing import FrontikTestBase


# from tests.instances import frontik_re_app, frontik_test_app

# re_app/pages/handler_404.py

# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import not_found_router, regex_router
#
#
# @not_found_router.get('__not_found', cls=PageHandler)
# @regex_router.get('/id/(?P<id1>[^/]+)/(?P<id2>[^/]+)', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     handler.text = '404'
#     handler.set_status(404)


# re_app/pages/id_param.py

# import lxml.etree as etree
#
# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import regex_router
#
#
# @regex_router.get('/id/(?P<id>[^/]+)', cls=PageHandler)
# async def get_page(handler: PageHandler = get_current_handler()) -> None:
#     handler.set_xsl('id_param.xsl')
#     handler.doc.put(etree.Element('id', value=handler.get_path_argument('id', 'wrong')))


# re_app/pages/simple.py

# from lxml import etree
#
# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import router
#
#
# @router.get('/simple', cls=PageHandler)
# async def get_page1(handler=get_current_handler()):
#     return await get_page(handler)
#
#
# @router.get('/not_simple', cls=PageHandler)
# async def get_page2(handler: PageHandler = get_current_handler()) -> None:
#     return await get_page(handler)
#
#
# async def get_page(handler: PageHandler) -> None:
#     handler.set_xsl('simple.xsl')
#     handler.doc.put(etree.Element('ok'))


@router.get('/simple')
async def get_page1():
    return 'ok'


@regex_router.get('/id/(?P<id>[^/]+)')
async def get_page(request: Request) -> None:
    return request.path_params.get('id')


@router.get('/nested/nested/nested')
async def get_page():
    return 'OK'


class TestRouting(FrontikTestBase):
    # Шляпа, тестинг фастапи роутинга
    # def test_regexp(self):
    #     html = frontik_re_app.get_page_text('not_simple')
    #     assert 'ok' in html

    # def test_file_mapping(self):
    #     html = frontik_test_app.get_page_text('simple_xml')
    #     assert 'ok' in html

    # def test_fallback_file_mapping(self):
    #     html = frontik_re_app.get_page_text('/simple')
    #     assert 'ok' in html

    async def test_extra_slash_in_mapping(self):
        response = await self.fetch('//not_simple')
        assert response.status_code == 404

    async def test_rewrite_single(self):
        response = await self.fetch('/id/some')
        assert response.data == 'some'

    async def test_rewrite_multiple(self) -> None:
        response = await self.fetch('/id/some,another')
        assert response.data == 'some,another'

    async def test_not_found(self):
        response = await self.fetch('/not_exists')
        assert response.status_code == 404

    # какие-то беспонтовые проверки на 404, наверное надо в фпх
    # def test_error_on_import(self) -> None:
    #     response = frontik_test_app.get_page('error_on_import')
    #     assert response.status_code == 404
    #
    # def test_error_on_import_of_module_having_module_not_found_error(self) -> None:
    #     response = frontik_test_app.get_page('module_not_found_error_on_import')
    #     assert response.status_code == 404
    #
    #     response = frontik_test_app.get_page('module_starting_same_as_page_not_found_error_on_import')
    #     assert response.status_code == 404

    # def test_frontik_router_custom_404(self):
    #     response = frontik_re_app.get_page('not_matching_regex')
    #     assert response.status_code == 404
    #     assert response.content == b'404'

    # def test_filemapping_default_404(self):
    #     response = frontik_test_app.get_page('no_page')
    #     assert response.status_code == 404
    #     assert response.content == b'<html><title>404: Not Found</title><body>404: Not Found</body></html>'

    async def test_filemapping_404_on_dot_in_url(self):
        response = await self.fetch('/nested/nested.nested')
        assert response.status_code == 404

    # def test_filemapping_custom_404(self):
    #     response = frontik_re_app.get_page('inexistent_page')
    #     assert response.status_code == 404
    #     assert response.content == b'404'

    # def test_filemapping_custom_404_for_complex_path(self):
    #     response = frontik_re_app.get_page('inexistent_page1/inexistent_page2')
    #     assert response.status_code == 404
    #     assert response.content == b'404'

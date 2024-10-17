# штука, которая тестит хэндлер и должна быть в fph


# test_app/pages/xsl/simple.py

# from lxml import etree
#
# from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, get_current_handler
# from frontik.routing import plain_router
#
#
# @plain_router.get('/xsl/simple', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     handler.set_xsl(handler.get_query_argument('template', 'simple.xsl'))
#     handler.doc.put(etree.Element('ok'))
#
#     if handler.get_query_argument('raise', 'false') == 'true':
#         handler.doc.put(etree.Element('not-ok'))
#         raise HTTPErrorWithPostprocessors(400)


# test_app/pages/xsl/apply_error.py

# from lxml import etree
#
# from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, get_current_handler
# from frontik.routing import plain_router
#
#
# @plain_router.get('/xsl/simple', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     handler.set_xsl(handler.get_query_argument('template', 'simple.xsl'))
#     handler.doc.put(etree.Element('ok'))
#
#     if handler.get_query_argument('raise', 'false') == 'true':
#         handler.doc.put(etree.Element('not-ok'))
#         raise HTTPErrorWithPostprocessors(400)


# test_app/pages/xsl/parse_error.py

# from tests.instances import frontik_test_app
# from lxml import etree
#
# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import plain_router
#
#
# @plain_router.get('/xsl/parse_error', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     handler.set_xsl('parse_error.xsl')
#     handler.doc.put(etree.Element('ok'))


# test_app/pages/xsl/syntax_error.py

# from lxml import etree
#
# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import plain_router
#
#
# @plain_router.get('/xsl/syntax_error', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     handler.set_xsl('syntax_error.xsl')
#     handler.doc.put(etree.Element('ok'))


# test_app/pages/cdata.py

# from lxml import etree
# 
# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import plain_router
# 
# CDATA_XML = b'<root><![CDATA[test<ba//d>]]></root>'
# 
# 
# @plain_router.get('/cdata', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     result = await handler.post_url(handler.get_header('host'), handler.path)
# 
#     xpath = result.data.xpath('/doc/*')
#     assert len(xpath) == 1
#     assert etree.tostring(xpath[0]) == CDATA_XML
# 
#     handler.doc.put(xpath)
# 
# 
# @plain_router.post('/cdata', cls=PageHandler)
# async def post_page(handler=get_current_handler()):
#     parser = etree.XMLParser(encoding='UTF-8', strip_cdata=False)
#     root = etree.XML(CDATA_XML, parser)
#     handler.doc.put(root)
#

# test_app/pages/include_xml.py

# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import plain_router
# 
# 
# @plain_router.get('/include_xml', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     handler.doc.put(handler.xml_from_file('aaa.xml'))
#

# test_app/pages/simple_xml.py

# from lxml import etree
# 
# import frontik.doc
# import frontik.handler
# from frontik.handler import PageHandler, get_current_handler
# from frontik.routing import plain_router
# 
# 
# @plain_router.get('/simple_xml', cls=PageHandler)
# async def get_page(handler=get_current_handler()):
#     handler.doc.put(frontik.doc.Doc())
#     handler.doc.put(etree.Element('element', name='Test element'))
#     handler.doc.put(frontik.doc.Doc(root_node='ok'))


# TEST
# class TestXsl:
#     def test_xsl_transformation(self):
#         response = frontik_test_app.get_page('xsl/simple')
#         assert response.headers['content-type'].startswith('text/html') is True
#         assert response.content == b'<html><body><h1>ok</h1></body></html>\n'
#
#     def test_xsl_apply_error(self):
#         response = frontik_test_app.get_page('xsl/apply_error')
#         assert response.status_code == 500
#
#         html = frontik_test_app.get_page_text('xsl/apply_error?debug')
#         assert 'XSLT ERROR in file' in html
#
#     def test_xsl_parse_error(self):
#         response = frontik_test_app.get_page('xsl/parse_error')
#         assert response.status_code == 500
#
#         html = frontik_test_app.get_page_text('xsl/parse_error?debug')
#         assert 'failed parsing XSL file parse_error.xsl (XSL parse error)' in html
#
#     def test_xsl_syntax_error(self):
#         response = frontik_test_app.get_page('xsl/syntax_error')
#         assert response.status_code == 500
#
#         html = frontik_test_app.get_page_text('xsl/syntax_error?debug')
#         assert 'failed parsing XSL file syntax_error.xsl (XML syntax)' in html
#
#     def test_no_xsl_template(self):
#         response = frontik_test_app.get_page('xsl/simple?template=no.xsl')
#         assert response.status_code == 500
#
#         html = frontik_test_app.get_page_text('xsl/simple?template=no.xsl&debug')
#         assert 'failed loading XSL file no.xsl' in html
#
#     def test_no_xsl_mode(self):
#         response = frontik_test_app.get_page('xsl/simple', notpl=True)
#         assert response.headers['content-type'].startswith('application/xml') is True
#
#     def test_cdata(self):
#         html = frontik_test_app.get_page_text('cdata')
#         assert 'test' in html
#         assert 'CDATA' in html
#
#     def test_xml_include(self):
#         xml = frontik_test_app.get_page_xml('include_xml')
#         assert xml.findtext('a') == 'aaa'
#
#     def test_root_node_frontik_attribute(self):
#         xml = frontik_test_app.get_page_xml('simple_xml')
#         assert xml.find('element').get('name') == 'Test element'
#         assert xml.find('doc').get('frontik', None) is None

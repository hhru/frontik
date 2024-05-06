from tests.instances import frontik_test_app


class TestXsl:
    def test_xsl_transformation(self):
        response = frontik_test_app.get_page('xsl/simple')
        assert response.headers['content-type'].startswith('text/html') is True
        assert response.content == b'<html><body><h1>ok</h1></body></html>\n'

    def test_xsl_apply_error(self):
        response = frontik_test_app.get_page('xsl/apply_error')
        assert response.status_code == 500

        html = frontik_test_app.get_page_text('xsl/apply_error?debug')
        assert 'XSLT ERROR in file' in html

    def test_xsl_parse_error(self):
        response = frontik_test_app.get_page('xsl/parse_error')
        assert response.status_code == 500

        html = frontik_test_app.get_page_text('xsl/parse_error?debug')
        assert 'failed parsing XSL file parse_error.xsl (XSL parse error)' in html

    def test_xsl_syntax_error(self):
        response = frontik_test_app.get_page('xsl/syntax_error')
        assert response.status_code == 500

        html = frontik_test_app.get_page_text('xsl/syntax_error?debug')
        assert 'failed parsing XSL file syntax_error.xsl (XML syntax)' in html

    def test_no_xsl_template(self):
        response = frontik_test_app.get_page('xsl/simple?template=no.xsl')
        assert response.status_code == 500

        html = frontik_test_app.get_page_text('xsl/simple?template=no.xsl&debug')
        assert 'failed loading XSL file no.xsl' in html

    def test_no_xsl_mode(self):
        response = frontik_test_app.get_page('xsl/simple', notpl=True)
        assert response.headers['content-type'].startswith('application/xml') is True

    def test_cdata(self):
        html = frontik_test_app.get_page_text('cdata')
        assert 'test' in html
        assert 'CDATA' in html

    def test_xml_include(self):
        xml = frontik_test_app.get_page_xml('include_xml')
        assert xml.findtext('a') == 'aaa'

    def test_root_node_frontik_attribute(self):
        xml = frontik_test_app.get_page_xml('simple_xml')
        assert xml.find('element').get('name') == 'Test element'
        assert xml.find('doc').get('frontik', None) is None

from tests.instances import frontik_test_app


class TestDoc:
    def test_doc_page(self):
        xml = frontik_test_app.get_page_xml('compose_doc')

        assert xml.find('a') is not None
        assert xml.findtext('a') == 'aaa'

        assert xml.find('bbb') is not None

        assert xml.find('c') is not None
        assert xml.findtext('c') in (None, '')

    def test_doc_invalid_xml(self):
        xml = frontik_test_app.get_page_xml('compose_doc?invalid=true')

        assert xml.find('error') is not None
        assert xml.find('error').get('reason') == 'invalid xml'

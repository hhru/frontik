from tests.instances import frontik_re_app, frontik_test_app


class TestRouting:
    def test_regexp(self):
        html = frontik_re_app.get_page_text('not_simple')
        assert 'ok' in html

    def test_file_mapping(self):
        html = frontik_test_app.get_page_text('simple_xml')
        assert 'ok' in html

    def test_fallback_file_mapping(self):
        html = frontik_re_app.get_page_text('simple')
        assert 'ok' in html

    def test_extra_slash_in_mapping(self):
        assert frontik_re_app.get_page('//not_simple').status_code == 200

    def test_rewrite_single(self):
        html = frontik_re_app.get_page_text('id/some')
        assert 'some' in html

    def test_rewrite_multiple(self) -> None:
        values = ('some', 'another')
        html = frontik_re_app.get_page_text('id/{}'.format(','.join(values)))
        assert all(map(html.find, values)) is True

    def test_error_on_import(self) -> None:
        response = frontik_test_app.get_page('error_on_import')
        assert response.status_code == 404

    def test_error_on_import_of_module_having_module_not_found_error(self) -> None:
        response = frontik_test_app.get_page('module_not_found_error_on_import')
        assert response.status_code == 404

        response = frontik_test_app.get_page('module_starting_same_as_page_not_found_error_on_import')
        assert response.status_code == 404

    def test_frontik_router_custom_404(self):
        response = frontik_re_app.get_page('not_matching_regex')
        assert response.status_code == 404
        assert response.content == b'404'

    def test_filemapping_default_404(self):
        response = frontik_test_app.get_page('no_page')
        assert response.status_code == 404
        assert response.content == b'<html><title>404: Not Found</title><body>404: Not Found</body></html>'

    def test_filemapping_404_on_dot_in_url(self):
        assert frontik_test_app.get_page('/nested/nested.nested').status_code == 404

    def test_filemapping_custom_404(self):
        response = frontik_re_app.get_page('inexistent_page')
        assert response.status_code == 404
        assert response.content == b'404'

    def test_filemapping_custom_404_for_complex_path(self):
        response = frontik_re_app.get_page('inexistent_page1/inexistent_page2')
        assert response.status_code == 404
        assert response.content == b'404'

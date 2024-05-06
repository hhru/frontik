from tests.instances import frontik_no_debug_app, frontik_re_app, frontik_test_app


class TestJinja:
    def test_jinja(self):
        response = frontik_test_app.get_page('json_page')
        assert response.headers['content-type'].startswith('text/html') is True
        assert response.content == b'<html><body><b>1</b><i>2</i></body></html>'

    def test_jinja_custom_render(self):
        response = frontik_test_app.get_page('json_page?custom_render=true')
        assert response.headers['content-type'].startswith('text/html') is True
        assert response.content == b'<html><body><b>custom1</b><i>custom2</i></body></html>'

    def test_jinja_custom_environment(self):
        response = frontik_re_app.get_page('jinja_custom_environment')
        assert response.content == b'<html><body>custom_env_function_value</body></html>'

    def test_jinja_no_environment(self) -> None:
        response = frontik_no_debug_app.get_page('jinja_no_environment')
        assert response.status_code == 500

    def test_jinja_no_template_exists(self):
        response = frontik_test_app.get_page('json_page?template=no.html')
        assert response.status_code == 500

        response = frontik_test_app.get_page('json_page?template=no.html', notpl=True)
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('application/json') is True

    def test_jinja_template_bad_data(self):
        response = frontik_test_app.get_page('json_page?template_error=true')
        assert response.status_code == 500

        debug_response = frontik_test_app.get_page('json_page?template_error=true&debug')
        assert b"'req1' is undefined" in debug_response.content

    def test_jinja_template_syntax_error(self):
        response = frontik_test_app.get_page('json_page?template=jinja-syntax-error.html')
        assert response.status_code == 500

        debug_response = frontik_test_app.get_page('json_page?template=jinja-syntax-error.html&debug')
        assert b"unexpected '}'" in debug_response.content

import unittest

from .instances import frontik_re_app, frontik_test_app


class TestJinja(unittest.TestCase):
    def test_jinja_ok(self):
        response = frontik_test_app.get_page('json_page')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, b'<html><body><b>1</b><i>2</i></body></html>')

    def test_jinja_custom_render(self):
        response = frontik_test_app.get_page('json_page?custom_render=true')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, b'<html><body><b>custom1</b><i>custom2</i></body></html>')

    def test_jinja_no_template_root(self):
        response = frontik_re_app.get_page('json_no_tpl_root')
        self.assertEqual(response.status_code, 500)

    def test_jinja_no_template_exists(self):
        response = frontik_test_app.get_page('json_page?template=no.html')
        self.assertEqual(response.status_code, 500)

        response = frontik_test_app.get_page('json_page?template=no.html', notpl=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['content-type'].startswith('application/json'))

    def test_jinja_template_bad_data(self):
        response = frontik_test_app.get_page('json_page?template_error=true')
        self.assertEqual(response.status_code, 500)

        debug_response = frontik_test_app.get_page('json_page?template_error=true&debug')
        self.assertIn(b"'req1' is undefined", debug_response.content)

    def test_jinja_template_syntax_error(self):
        response = frontik_test_app.get_page('json_page?template=jinja-syntax-error.html')
        self.assertEqual(response.status_code, 500)

        debug_response = frontik_test_app.get_page('json_page?template=jinja-syntax-error.html&debug')
        self.assertIn(b"unexpected '}'", debug_response.content)

import unittest

from frontik.routing import MAX_MODULE_NAME_LENGTH

from .instances import frontik_re_app, frontik_test_app


class TestRouting(unittest.TestCase):
    def test_regexp(self):
        html = frontik_re_app.get_page_text('not_simple')
        self.assertIn('ok', html)

    def test_file_mapping(self):
        html = frontik_test_app.get_page_text('simple_xml')
        self.assertIn('ok', html)

    def test_fallback_file_mapping(self):
        html = frontik_re_app.get_page_text('simple')
        self.assertIn('ok', html)

    def test_extra_slash_in_regex(self):
        """Routes specified with regexps should match precisely"""
        self.assertEqual(frontik_re_app.get_page('//not_simple').status_code, 404)

    def test_extra_slash_in_mapping(self):
        """Routes specified as mappings to filesystem can contain extra slashes"""
        self.assertEqual(frontik_re_app.get_page('//simple').status_code, 200)
        self.assertEqual(frontik_test_app.get_page('//nested///nested//////nested').status_code, 200)

    def test_module_name_too_large(self):
        self.assertEqual(frontik_test_app.get_page('/' + 'a' * (MAX_MODULE_NAME_LENGTH + 1)).status_code, 404)

    def test_rewrite_single(self):
        html = frontik_re_app.get_page_text('id/some')
        self.assertIn('some', html)

    def test_rewrite_multiple(self):
        values = ('some', 'another')
        html = frontik_re_app.get_page_text('id/{}'.format(','.join(values)))
        self.assertTrue(all(map(html.find, values)))

    def test_error_on_import(self):
        response = frontik_test_app.get_page('error_on_import')
        self.assertEqual(response.status_code, 500)

    def test_frontik_router_custom_404(self):
        response = frontik_re_app.get_page('not_matching_regex')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, b'404')

    def test_filemapping_default_404(self):
        response = frontik_test_app.get_page('no_page')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, b'<html><title>404: Not Found</title><body>404: Not Found</body></html>')

    def test_filemapping_404_on_dot_in_url(self):
        self.assertEqual(frontik_test_app.get_page('/nested/nested.nested').status_code, 404)

    def test_filemapping_custom_404(self):
        response = frontik_re_app.get_page('inexistent_page')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, b'404')

    def test_reverse_url(self):
        json = frontik_re_app.get_page_json('reverse_url')
        self.assertEqual(json, {
            'args': '/id/1/2',
            'args_and_kwargs': '/id/1/2',
            'kwargs': '/id/1/2',
        })

    def test_reverse_url_fail(self):
        response = frontik_re_app.get_page('reverse_url?fail_args=true')
        self.assertEqual(response.status_code, 500)

        response = frontik_re_app.get_page('reverse_url?fail_missing=true')
        self.assertEqual(response.status_code, 500)

import unittest

from tests.instances import frontik_test_app

POSTPROCESS_URL = 'postprocess/?{}'


class TestPostprocessors(unittest.TestCase):
    def test_no_postprocessors(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format(''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'<html><h1>%%header%%</h1>%%content%%</html>')

    def test_postprocessors_raise_error(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('raise_error'))
        self.assertEqual(response.status_code, 400)

    def test_postprocessors_finish(self):
        response = frontik_test_app.get_page_text(POSTPROCESS_URL.format('finish'))
        self.assertEqual(response, 'FINISH_IN_PP')

    def test_render_postprocessors_single(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('header'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'<html><h1>HEADER</h1>%%content%%</html>')

    def test_render_postprocessors_multiple(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('header&content'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'<html><h1>HEADER</h1>CONTENT</html>')

    def test_render_postprocessors_notpl(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('content&notpl'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"content":"CONTENT"}')

    def test_metainfo_in_xsl_postprocessor(self):
        response = frontik_test_app.get_page('/postprocess_xsl?meta_key=my_meta_key')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'my_meta_key')

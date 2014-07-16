# coding=utf-8

import unittest

from .instances import frontik_test_app

POSTPROCESS_URL = 'postprocess/?{}'


class TestPostprocessors(unittest.TestCase):
    def test_no_postprocessors(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format(''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '<html><h1>%%header%%</h1>%%content%%</html>')

    def test_early_postprocessors(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('fail_early'))
        self.assertEqual(response.status_code, 400)

    def test_template_postprocessors_single(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('header'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '<html><h1>HEADER</h1>%%content%%</html>')

    def test_template_postprocessors_multiple(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('header&content'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '<html><h1>HEADER</h1>CONTENT</html>')

    def test_template_postprocessors_nopost(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('nopost'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '<html><h1>%%header%%</h1>%%content%%</html>')

    def test_late_postprocessors(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('nocache&addserver'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-cache')
        self.assertEqual(response.headers['server'], 'Frontik')

    def test_late_postprocessors_after_error(self):
        response = frontik_test_app.get_page(POSTPROCESS_URL.format('fail_early&nocache&addserver'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers['cache-control'], 'no-cache')
        self.assertEqual(response.headers['server'], 'Frontik')

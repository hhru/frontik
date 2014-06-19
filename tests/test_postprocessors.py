# coding=utf-8

import unittest

from tests.instances import frontik_debug

POSTPROCESS_URL = 'test_app/postprocess/?{}'


class TestPostprocessors(unittest.TestCase):
    def test_no_postprocessors(self):
        response = frontik_debug.get_page(POSTPROCESS_URL.format(''))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.content, '<html>\n<h1>{{header}}</h1>{{content}}\n</html>\n')

    def test_early_postprocessors(self):
        response = frontik_debug.get_page(POSTPROCESS_URL.format('fail_early'))
        self.assertEquals(response.status_code, 400)

    def test_template_postprocessors_single(self):
        response = frontik_debug.get_page(POSTPROCESS_URL.format('header'))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.content, '<html>\n<h1>HEADER</h1>{{content}}\n</html>\n')

    def test_template_postprocessors_multiple(self):
        response = frontik_debug.get_page(POSTPROCESS_URL.format('header&content'))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.content, '<html>\n<h1>HEADER</h1>CONTENT\n</html>\n')

    def test_late_postprocessors(self):
        response = frontik_debug.get_page(POSTPROCESS_URL.format('nocache&addserver'))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.headers['cache-control'], 'no-cache')
        self.assertEquals(response.headers['server'], 'Frontik')

    def test_late_postprocessors_after_error(self):
        response = frontik_debug.get_page(POSTPROCESS_URL.format('fail_early&nocache&addserver'))
        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.headers['cache-control'], 'no-cache')
        self.assertEquals(response.headers['server'], 'Frontik')

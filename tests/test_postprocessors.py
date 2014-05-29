# coding=utf-8

import unittest

import urllib2

from tests import frontik_debug

POSTPROCESS_URL = 'http://localhost:{0}/test_app/postprocess/?{1}'


class TestPostprocessors(unittest.TestCase):
    def test_no_postprocessors(self):
        with frontik_debug.instance() as srv_port:
            try:
                response = urllib2.urlopen(POSTPROCESS_URL.format(srv_port, ''))
                self.assertEquals(response.code, 200)
                self.assertEquals(response.read(), '<html>\n<h1>{{header}}</h1>{{content}}\n</html>\n')
            except Exception:
                assert False

    def test_early_postprocessors(self):
        with frontik_debug.instance() as srv_port:
            try:
                urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'fail_early'))
                self.fail('page should fail with 400')
            except Exception as e:
                self.assertEquals(e.code, 400)

    def test_template_postprocessors_single(self):
        with frontik_debug.instance() as srv_port:
            try:
                response = urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'header'))
                self.assertEquals(response.code, 200)
                self.assertEquals(response.read(), '<html>\n<h1>HEADER</h1>{{content}}\n</html>\n')
            except Exception:
                self.fail('page should not fail')

    def test_template_postprocessors_multiple(self):
        with frontik_debug.instance() as srv_port:
            try:
                response = urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'header&content'))
                self.assertEquals(response.code, 200)
                self.assertEquals(response.read(), '<html>\n<h1>HEADER</h1>CONTENT\n</html>\n')
            except Exception:
                self.fail('page should not fail')

    def test_late_postprocessors(self):
        with frontik_debug.instance() as srv_port:
            try:
                response = urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'nocache&addserver'))
                self.assertEquals(response.code, 200)
                self.assertEquals(response.headers['cache-control'], 'no-cache')
                self.assertEquals(response.headers['server'], 'Frontik')
            except Exception:
                self.fail('page should not fail')

    def test_late_postprocessors_after_error(self):
        with frontik_debug.instance() as srv_port:
            try:
                urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'fail_early&nocache&addserver'))
                self.fail('page should fail with 400')
            except Exception as e:
                self.assertEquals(e.code, 400)
                self.assertEquals(e.headers['cache-control'], 'no-cache')
                self.assertEquals(e.headers['server'], 'Frontik')

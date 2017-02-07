# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestPreprocessors(unittest.TestCase):
    def test_preprocessors(self):
        response = frontik_test_app.get_page('preprocessors')
        self.assertEqual(response.content, b'1 2 3 (1 2 3 4) 5 6')
        self.assertEqual(response.headers['Content-Type'], 'text/plain')

    def test_preprocessors_nocallback(self):
        text = frontik_test_app.get_page_text('preprocessors?nocallback=true')
        self.assertEqual(text, '1 2 3')

    def test_preprocessors_fail(self):
        response = frontik_test_app.get_page('preprocessors?fail=true')
        self.assertEqual(response.status_code, 503)

    def test_preprocessors_new(self):
        response_json = frontik_test_app.get_page_json('preprocessors_new')
        self.assertEqual(
            response_json,
            {
                'run': [
                    'pp01', 'pp02', 'pp1-before-yield', 'pp1-between-yield', 'pp1-after-yield', 'pp2', 'pp3', 'get_page'
                ],
                'post': ['pp01', 'pp02'],
                'postprocessor': True
            }
        )

    def test_preprocessors_new_finish_with_postprocessors(self):
        response_json = frontik_test_app.get_page_json('preprocessors_new?finish_with_postprocessors=true')
        self.assertEqual(
            response_json,
            {
                'run': ['pp01', 'pp02', 'pp1-before-yield', 'pp1-between-yield', 'pp1-after-yield', 'pp2'],
                'postprocessor': True
            }
        )

    def test_preprocessors_new_raise_error(self):
        response = frontik_test_app.get_page('preprocessors_new?raise_error=true')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'<html><title>400: Bad Request</title><body>400: Bad Request</body></html>')

    def test_preprocessors_new_finish(self):
        response = frontik_test_app.get_page_text('preprocessors_new?finish=true')
        self.assertEqual(response, 'finished')

    def test_preprocessors_new_redirect(self):
        response = frontik_test_app.get_page('preprocessors_new?redirect=true', allow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('redirected', response.headers.get('Location'))

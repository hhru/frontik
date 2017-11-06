# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestPreprocessors(unittest.TestCase):
    def test_preprocessors_new(self):
        response_json = frontik_test_app.get_page_json('preprocessors')
        self.assertEqual(
            response_json,
            {
                'run': [
                    'pp01', 'pp02', 'pp1-before', 'pp1-between', 'pp1-after', 'pp2', 'pp3', 'get_page'
                ],
                'put_request_finished': True,
                'put_request_preprocessors': ['pp01', 'pp02'],
                'postprocessor': True
            }
        )

    def test_preprocessors_new_abort_and_run_postprocessors(self):
        response_json = frontik_test_app.get_page_json('preprocessors?abort_and_run_postprocessors=true')
        self.assertEqual(
            response_json,
            {
                'run': ['pp01', 'pp02', 'pp1-before', 'pp1-between', 'pp1-after', 'pp2'],
                'postprocessor': True
            }
        )

    def test_preprocessors_new_wait_and_run_postprocessors(self):
        response_json = frontik_test_app.get_page_json('preprocessors?wait_and_run_postprocessors=true')
        self.assertEqual(
            response_json,
            {
                'run': ['pp01', 'pp02', 'pp1-before', 'pp1-between', 'pp1-after', 'pp2'],
                'put_request_finished': True,
                'postprocessor': True
            }
        )

    def test_preprocessors_new_raise_error(self):
        response = frontik_test_app.get_page('preprocessors?raise_error=true')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'<html><title>400: Bad Request</title><body>400: Bad Request</body></html>')

    def test_preprocessors_new_finish(self):
        response = frontik_test_app.get_page_text('preprocessors?finish=true')
        self.assertEqual(response, 'finished')

    def test_preprocessors_new_redirect(self):
        response = frontik_test_app.get_page('preprocessors?redirect=true', allow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('redirected', response.headers.get('Location'))

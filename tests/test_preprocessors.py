import json
import unittest

import requests

from .instances import frontik_test_app


class TestPreprocessors(unittest.TestCase):
    def test_preprocessors(self):
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

    def test_error_in_callback(self):
        response = frontik_test_app.get_page('preprocessors?raise_error_in_callback=true')
        self.assertEqual(response.status_code, 403)

    def test_preprocessor_futures(self):
        response_json = frontik_test_app.get_page_json('preprocessors/preprocessor_futures')
        self.assertEqual(
            response_json,
            {
                'preprocessors': [
                    'should_finish_first',
                    'should_finish_second',
                    'should_finish_third'
                ]
            }
        )

    def test_add_preprocessor_future_after_preprocessors(self):
        response = frontik_test_app.get_page('preprocessors/preprocessor_futures', method=requests.post)
        self.assertEqual(response.status_code, 500)

    def test_add_preprocessor_future_return_value(self):
        response_json = frontik_test_app.get_page_json('preprocessors/preprocessor_future_return')
        self.assertEqual(response_json, {'test': 'test'})

    def test_preprocessors_abort(self):
        response_json = frontik_test_app.get_page_json('preprocessors/aborted?abort_preprocessors=true')
        self.assertEqual(
            response_json, {'run': ['before', 'pp'], 'put_request_finished': True, 'postprocessor': True}
        )

    def test_preprocessors_abort_nowait(self):
        response_json = frontik_test_app.get_page_json('preprocessors/aborted?abort_preprocessors_nowait=true')
        self.assertEqual(
            response_json, {'run': ['before', 'pp'], 'postprocessor': True}
        )

    def test_preprocessors_raise_error(self):
        response = frontik_test_app.get_page('preprocessors/aborted?raise_error=true')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'<html><title>400: Bad Request</title><body>400: Bad Request</body></html>')

    def test_preprocessors_raise_custom_error(self):
        response = frontik_test_app.get_page('preprocessors/aborted?raise_custom_error=true')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content), {'custom_error': True, 'postprocessor': True})

    def test_preprocessors_finish(self):
        response = frontik_test_app.get_page_text('preprocessors/aborted?finish=true')
        self.assertEqual(response, 'finished')

    def test_preprocessors_redirect(self):
        response = frontik_test_app.get_page('preprocessors/aborted?redirect=true', allow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('redirected', response.headers.get('Location'))

    def test_finish_in_nonblocking_group_preprocessor(self):
        response = frontik_test_app.get_page('preprocessors/aborted_nonblocking_group?finish=true')
        self.assertEqual(response.content, b'DONE_IN_PP')
        self.assertEqual(response.status_code, 400)

    def test_abort_in_nonblocking_group_preprocessor(self):
        response = frontik_test_app.get_page('preprocessors/aborted_nonblocking_group?abort=true')
        self.assertEqual(response.status_code, 200)

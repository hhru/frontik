import unittest

import requests

from .instances import frontik_test_app


class TestFinishWithPostprocessors(unittest.TestCase):
    def test_finish_with_postprocessors(self):
        type_to_content = {
            'text': b'ok',
            'xml': b"<?xml version='1.0' encoding='utf-8'?>\n<doc><ok/></doc>",
            'xsl': b"<html><body><h1>ok</h1></body></html>\n",
            'json': b'{"ok": true}',
        }

        for content_type, content in type_to_content.items():
            response = frontik_test_app.get_page(f'finish_with_postprocessors?type={content_type}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, content)
            self.assertEqual(response.headers['X-Foo'], 'Bar')

    def test_abort_handler(self):
        get_result = frontik_test_app.get_page_json('write_after_finish')
        post_result = frontik_test_app.get_page_json('write_after_finish', method=requests.post)

        self.assertEqual(get_result['postprocessor_completed'], True)
        self.assertEqual(post_result['counter'], 1)

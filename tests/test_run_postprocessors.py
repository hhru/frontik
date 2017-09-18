# coding=utf-8

import unittest

from frontik.compat import iteritems
from .instances import frontik_test_app


class TestFinishWithPostprocessors(unittest.TestCase):
    def test_run_postprocessors(self):
        type_to_content = {
            'text': b'ok',
            'xml': b"<?xml version='1.0' encoding='utf-8'?>\n<doc><ok/></doc>",
            'xsl': b"<html><body><h1>ok</h1></body></html>\n",
            'json': b'{"ok": true}',
        }

        for content_type, content in iteritems(type_to_content):
            response = frontik_test_app.get_page('run_postprocessors?type={}'.format(content_type))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, content)
            self.assertEqual(response.headers['X-Foo'], 'Bar')

# coding=utf-8

import unittest

from frontik.compat import iteritems
from .instances import frontik_test_app


class TestHandler(unittest.TestCase):
    def test_finish_with_content(self):
        type_to_content = {
            'text': b'ok',
            'xml': b"<?xml version='1.0' encoding='utf-8'?>\n<doc><ok/></doc>",
            'json': b'{"ok": true}',
        }

        for content_type, content in iteritems(type_to_content):
            response = frontik_test_app.get_page('finish_with_content?type={}'.format(content_type))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, content)
            self.assertEqual(response.headers['X-Foo'], 'Bar')

    def test_finish_with_content_status_code(self):
        response = frontik_test_app.get_page('finish_with_content?type=text&code=403')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'ok')
        self.assertEqual(response.headers['X-Foo'], 'Bar')

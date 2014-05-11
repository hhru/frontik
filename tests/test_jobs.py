# coding=utf-8

import unittest

from tests.instances import frontik_debug


class TestXsl(unittest.TestCase):
    def test_job_fail(self):
        response = frontik_debug.get_page('test_app/job_fail')
        self.assertEquals(response.status_code, 400)

        html = frontik_debug.get_page_text('test_app/job_fail?nofail=True')
        self.assertIsNotNone(html.find('ok'))

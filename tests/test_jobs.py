# coding=utf-8

import unittest

from . import py3_skip
from .instances import frontik_test_app


class TestJobs(unittest.TestCase):
    @py3_skip
    def test_job_fail(self):
        response = frontik_test_app.get_page('job_fail')
        self.assertEqual(response.status_code, 400)

        html = frontik_test_app.get_page_text('job_fail?nofail=True')
        self.assertIn('ok', html)

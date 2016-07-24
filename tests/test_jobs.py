# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestJobs(unittest.TestCase):
    def test_job_fail(self):
        response = frontik_test_app.get_page('job_fail')
        self.assertEqual(response.status_code, 400)

        xml = frontik_test_app.get_page_text('job_fail?nofail=True')
        self.assertIn('<ok result="True"/>', xml)

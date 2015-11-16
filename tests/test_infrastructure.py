# coding=utf-8

import httplib
import socket
import sys
import unittest

from . import instances


class TestingInfrastructureTestCase(unittest.TestCase):
    def test_load_page_from_test_instances(self):
        for instance in (instances.frontik_test_app, instances.frontik_non_debug, instances.frontik_re_app):
            self.assertEquals(instance.get_page('status').status_code, httplib.OK)

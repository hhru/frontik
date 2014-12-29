# _*_ coding: utf-8 _*_
import unittest
import socket
import httplib
import sys

from . import instances


class TestingInfrastructureTestCase(unittest.TestCase):

    def test_bind_127_0_0_1(self):
        success = False
        for port in xrange(9000, 10000):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(('127.0.0.1', port))
                sock.close()
                success = True
                break
            except:
                continue
        self.assertTrue(success, 'Unable to bind 127.0.0.1 on ports 9000-9999')

    def test_load_page_from_test_instances(self):
        for instance in (instances.frontik_test_app,
                         instances.frontik_non_debug,
                         instances.frontik_re_app):
            sys.stderr.write('Check test instance for app "{}"\n'.format(instance.app))
            self.assertEquals(instance.get_page('status').status_code, httplib.OK)

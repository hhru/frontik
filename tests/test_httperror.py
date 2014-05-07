# coding=utf-8

import unittest
import urllib
import urllib2

from tests import frontik_debug


class TestExceptions(unittest.TestCase):
    def test_finish_with_httperror_200(self):
        with frontik_debug.instance() as srv_port:
            data = urllib2.urlopen('http://localhost:{0}/test_app/finish_page/'.format(srv_port)).read()
            self.assertEqual(data, 'success')

    def test_finish_with_httperror_401(self):
        with frontik_debug.instance() as srv_port:
            try:
                urllib2.urlopen('http://localhost:{0}/test_app/finish_401/'.format(srv_port))
                self.fail('Page should fail with 401 error code')
            except Exception as e:
                self.assertEqual(e.msg, 'Unauthorized')
                self.assertEqual(e.code, 401)
                self.assertEqual(e.headers['WWW-Authenticate'], 'Basic realm="Secure Area"')

    def test_httperror_text(self):
        with frontik_debug.instance() as srv_port:
            response = urllib.urlopen('http://localhost:{0}/test_app/test_exception_text/?port={0}'.format(srv_port))
            self.assertEqual(response.code, 403)
            self.assertEqual(response.read(), 'This is just a plain text')

    def test_httperror_xml_xsl(self):
        with frontik_debug.instance() as srv_port:
            response = urllib.urlopen('http://localhost:{0}/test_app/test_exception_xml_xsl'.format(srv_port))
            self.assertEqual(response.code, 302)
            self.assertEqual(response.read(), '<html><body>\n<h1>ok</h1>\n<h1>not ok</h1>\n</body></html>\n')

    def test_httperror_json(self):
        with frontik_debug.instance() as srv_port:
            response = urllib.urlopen('http://localhost:{0}/test_app/test_exception_json'.format(srv_port))
            self.assertEqual(response.code, 400)
            self.assertEqual(response.read(), '{"reason": "bad argument"}')

# coding=utf-8

import base64
import httplib
import unittest

from tornado.escape import to_unicode

from frontik.handler_debug import request_to_curl_string
from frontik.util import make_get_request, make_post_request, make_put_request
from .instances import create_basic_auth_header, frontik_non_debug


class CurlStringTestCase(unittest.TestCase):

    def test_curl_string_get(self):
        request = make_get_request(
            'http://test.com/path',
            data={'param': 'value'},
            headers={'Accept': 'application/json'}
        )

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X GET 'http://test.com/path?param=value' -H 'Accept: application/json'"
        )

    def test_curl_string_post(self):
        request = make_post_request('http://test.com/path', data={'param': 'value'})

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 11' "
            "-H 'Content-Type: application/x-www-form-urlencoded' --data 'param=value'"
        )

    def test_curl_string_put(self):
        request = make_put_request('http://test.com/path', data='DATA', content_type='text/plain')

        self.assertEqual(
            request_to_curl_string(request),
            "curl -X PUT 'http://test.com/path' -H 'Content-Length: 4' -H 'Content-Type: text/plain' --data 'DATA'"
        )

    def test_curl_string_binary(self):
        request = make_post_request('http://test.com/path', data=u'тест', content_type='text/plain')

        self.assertEqual(
            request_to_curl_string(request),
            "echo -e '\\xd1\\x82\\xd0\\xb5\\xd1\\x81\\xd1\\x82' | "
            "curl -X POST 'http://test.com/path' -H 'Content-Length: 4' -H 'Content-Type: text/plain' --data-binary @-"
        )


class DebugTestCase(unittest.TestCase):

    DEBUG_BASIC_AUTH = create_basic_auth_header('user:god')

    def test_complex_debug_page(self):
        response = frontik_non_debug.get_page(
            'app/debug?debug', headers={'Authorization': self.DEBUG_BASIC_AUTH}
        )

        self.assertEquals(response.status_code, 200)

        # Basic debug messages

        basic_messages = (
            'debug: starting debug page',
            'warning: testing simple inherited debug',
            'error: testing failing urls',
            'info: testing responses',
            'debug mode is ON',
            '<span class="entry__head__expandtext">XSLT profiling results</span>',
        )

        for msg in basic_messages:
            self.assertIn(msg, response.content)

        # Extra output and different types of content

        extra_output = (
            u'&lt;child2&gt;тест&lt;/child2&gt;',
            u'юникод\ndebug',
            u'"тест": "value"',
            u'SomeProtobufObject()',
            u'&lt;response&gt;some xml&lt;/response&gt;',
            u'document.body.write("Привет")',
            u'привет charset',
        )

        for msg in extra_output:
            self.assertIn(msg, to_unicode(response.content))

        # Iframes

        self.assertEqual(response.content.count("doiframe('"), 3)

        # Check that all http requests are present

        self.assertEqual(response.content.count('<div class="timebar">'), 15)

        # Inherited debug

        assert_occurs_twice = (
            'ValueError: Testing an exception',
            '<span class="entry__head__expandtext">Exception traceback</span>',
            '<span class="entry__head__expandtext">testing xml output</span>',
            '<span class="entry__head__expandtext">testing utf-8 text output</span>',
            '<span class="entry__head__expandtext">testing unicode text output</span>',
        )

        for msg in assert_occurs_twice:
            self.assertEqual(response.content.count(msg), 2)

        # Check that everything went right

        assert_not_found = (
            'cannot parse request body',
            'cannot parse response body',
            'cannot append time info',
            'cannot log response info',
            'cannot decode parameter name or value',
            'cannot add traceback lines',
            'error creating log entry with attrs',
            'XSLT debug file error',
        )

        for msg in assert_not_found:
            self.assertNotIn(msg, response.content)

    def assertDebugResponseCode(self, page, expected_code, headers=None):
        response = frontik_non_debug.get_page(page, headers=headers)
        self.assertEqual(response.status_code, expected_code)
        return response

    def test_debug_by_basic_auth(self):
        for param in ('debug', 'nopost', 'noxsl', 'notpl'):
            response = self.assertDebugResponseCode(page='app/simple_xml?{}'.format(param),
                                                    expected_code=httplib.UNAUTHORIZED)
            self.assertIn('Www-Authenticate', response.headers)
            self.assertRegexpMatches(response.headers['Www-Authenticate'], 'Basic realm="[^"]+"')

            self.assertDebugResponseCode(page='app/simple_xml?{}'.format(param),
                                         headers={'Authorization': self.DEBUG_BASIC_AUTH},
                                         expected_code=httplib.OK)

    def test_debug_by_basic_auth_with_invalid_header(self):
        invalid_headers = (
            'Token user:god',
            'Bearer abcdfe0123456789',
            'Basic',
            'Basic ',
            'Basic ScrewYou',
            create_basic_auth_header(':'),
            create_basic_auth_header(''),
            create_basic_auth_header('not:pass'),
            'BASIC {}'.format(base64.encodestring('user:god').strip())
        )

        for h in invalid_headers:
            self.assertDebugResponseCode('app/simple_xml?debug', httplib.UNAUTHORIZED, headers={'Authorization': h})

    def test_debug_by_header(self):
        for param in ('debug', 'nopost', 'noxsl', 'notpl'):
            response = self.assertDebugResponseCode('app/simple_xml?{}'.format(param), httplib.UNAUTHORIZED)

            self.assertIn('Www-Authenticate', response.headers)
            self.assertEqual('Basic realm="Secure Area"', response.headers['Www-Authenticate'])

            self.assertDebugResponseCode(
                'app/simple_xml?{}'.format(param), httplib.OK, headers={'Frontik-Debug-Auth': 'user:god'}
            )

            self.assertDebugResponseCode(
                'app/simple_xml?{}'.format(param), httplib.OK,
                headers={'Frontik-Debug-Auth': 'user:god', 'Authorization': 'Basic bad'}
            )

    def test_debug_by_header_with_wrong_header(self):
        for value in ('', 'not:pass', 'user: god', self.DEBUG_BASIC_AUTH):
            response = self.assertDebugResponseCode(
                'app/simple_xml?debug', httplib.UNAUTHORIZED, headers={'Frontik-Debug-Auth': value}
            )

            self.assertIn('Www-Authenticate', response.headers)
            self.assertEqual('Frontik-Debug-Auth-Header realm="Secure Area"', response.headers['Www-Authenticate'])

    def test_debug_by_cookie(self):
        for param in ('debug', 'noxsl', 'notpl', 'nopost'):
            self.assertDebugResponseCode(
                'app/simple_xml', httplib.UNAUTHORIZED, headers={'Cookie': '{}=true'.format(param)}
            )

            self.assertDebugResponseCode(
                'app/simple_xml', httplib.OK,
                headers={'Cookie': '{}=true;'.format(param), 'Authorization': self.DEBUG_BASIC_AUTH}
            )

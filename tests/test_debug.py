import base64
import http.client
import unittest

from tornado.escape import to_unicode

from .instances import create_basic_auth_header, frontik_test_app, frontik_no_debug_app


class DebugTestCase(unittest.TestCase):
    DEBUG_BASIC_AUTH = create_basic_auth_header('user:god')

    def test_complex_debug_page(self):
        response = frontik_test_app.get_page('debug?debug')
        response_content = to_unicode(response.content)

        self.assertEqual(response.status_code, 200)

        # Basic debug messages

        basic_messages = (
            'debug: starting debug page',
            'warning: testing simple inherited debug',
            'error: testing failing urls',
            'info: testing responses',
            '<span class="entry__head__expandtext">XSLT profiling results</span>',
        )

        for msg in basic_messages:
            self.assertIn(msg, response_content)

        # Extra output and different types of content

        extra_output = (
            '&lt;child2&gt;тест&lt;/child2&gt;',
            'юникод\ndebug',
            '"тест": "value"',
            'SomeProtobufObject()',
            '&lt;response&gt;some xml&lt;/response&gt;',
            'document.body.write("Привет")',
            'привет charset',
        )

        for msg in extra_output:
            self.assertIn(msg, response_content)

        # Check that all http requests are present

        self.assertEqual(response_content.count('<div class="timebar">'), 15)

        # Inherited debug

        assert_occurs_twice = (
            'ValueError: Testing an exception',
            '<span class="entry__head__expandtext">Exception traceback</span>',
            '<span class="entry__head__expandtext">testing xml output</span>',
            '<span class="entry__head__expandtext">testing utf-8 text output</span>',
            '<span class="entry__head__expandtext">testing unicode text output</span>',
        )

        for msg in assert_occurs_twice:
            self.assertEqual(response_content.count(msg), 2)

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
            self.assertNotIn(msg, response_content)

    def assertDebugResponseCode(self, page, expected_code, headers=None):
        response = frontik_no_debug_app.get_page(page, headers=headers)
        self.assertEqual(response.status_code, expected_code)
        return response

    def test_debug_by_basic_auth(self):
        for param in ('debug', 'noxsl', 'notpl'):
            response = self.assertDebugResponseCode(f'simple?{param}', http.client.UNAUTHORIZED)
            self.assertIn('Www-Authenticate', response.headers)
            self.assertRegex(response.headers['Www-Authenticate'], 'Basic realm="[^"]+"')

            self.assertDebugResponseCode(
                f'simple?{param}', http.client.OK, headers={'Authorization': self.DEBUG_BASIC_AUTH}
            )

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
            'BASIC {}'.format(to_unicode(base64.b64encode(b'user:god')))
        )

        for h in invalid_headers:
            self.assertDebugResponseCode('simple?debug', http.client.UNAUTHORIZED, headers={'Authorization': h})

    def test_debug_by_header(self):
        for param in ('debug', 'noxsl', 'notpl'):
            response = self.assertDebugResponseCode(f'simple?{param}', http.client.UNAUTHORIZED)

            self.assertIn('Www-Authenticate', response.headers)
            self.assertEqual('Basic realm="Secure Area"', response.headers['Www-Authenticate'])

            self.assertDebugResponseCode(
                f'simple?{param}', http.client.OK, headers={'Frontik-Debug-Auth': 'user:god'}
            )

            self.assertDebugResponseCode(
                f'simple?{param}', http.client.OK,
                headers={'Frontik-Debug-Auth': 'user:god', 'Authorization': 'Basic bad'}
            )

    def test_debug_by_header_with_wrong_header(self):
        for value in ('', 'not:pass', 'user: god', self.DEBUG_BASIC_AUTH):
            response = self.assertDebugResponseCode(
                'simple?debug', http.client.UNAUTHORIZED, headers={'Frontik-Debug-Auth': value}
            )

            self.assertIn('Www-Authenticate', response.headers)
            self.assertEqual('Frontik-Debug-Auth-Header realm="Secure Area"', response.headers['Www-Authenticate'])

    def test_debug_by_cookie(self):
        for param in ('debug', 'noxsl', 'notpl'):
            self.assertDebugResponseCode(
                'simple', http.client.UNAUTHORIZED, headers={'Cookie': f'{param}=true'}
            )

            self.assertDebugResponseCode(
                'simple', http.client.OK,
                headers={'Cookie': f'{param}=true;', 'Authorization': self.DEBUG_BASIC_AUTH}
            )

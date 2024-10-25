import base64
import http.client
import logging
import re
from typing import Optional

from fastapi import Query, Request, Response
from http_client import RequestResult
from lxml import etree
from lxml.builder import E
from tornado.escape import to_unicode

from frontik import media_types
from frontik.dependencies import HttpClient
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase
from tests import create_basic_auth_header

logger = logging.getLogger('handler')


@router.get('/debug')
async def get_debug_page(http_client: HttpClient, request: Request, no_recursion: str = 'false') -> None:
    logger.debug('debug: starting debug page')

    def _exception_trace() -> None:
        def _inner() -> None:
            raise ValueError('Testing an exception юникод')

        _inner()

    try:
        _exception_trace()
    except ValueError:
        logger.exception('exception catched')

    logger.warning('warning: testing simple inherited debug')
    await http_client.post_url(request.headers.get('host', 'no_host'), '/debug')

    logger.error('error: testing failing urls')
    await http_client.get_url('invalid_host', '/invalid_url')

    logger.info('info: testing responses')
    await http_client.put_url(request.headers.get('host', 'no_host'), '/debug?type=html')
    await http_client.put_url(request.headers.get('host', 'no_host'), '/debug?type=protobuf')
    await http_client.put_url(request.headers.get('host', 'no_host'), '/debug?type=xml')
    await http_client.put_url(request.headers.get('host', 'no_host'), '/debug?type=javascript')
    await http_client.put_url(request.headers.get('host', 'no_host'), '/debug?type=text')

    logger.debug('testing xml output', extra={'_xml': E.root(E.child1(param='тест'), E.child2('тест'))})
    logger.debug('testing utf-8 text output', extra={'_text': 'some\nmultiline\nюникод\ndebug'})
    logger.debug('testing unicode text output', extra={'_text': 'some\nmultiline\nюникод\ndebug'})

    if no_recursion != 'true':
        logger.debug('testing complex inherited debug')
        await http_client.get_url(request.headers.get('host', 'no_host'), '/debug?no_recursion=true&debug=xslt')


@router.post('/debug')
async def post_debug_page():
    logger.debug('this page returns json')

    return {'param1': 'value', 'param2': 'тест', 'тест': 'value'}


@router.put('/debug')
async def put_debug_page(content_type: str = Query(alias='type')) -> Response:
    if content_type == 'html':
        return Response('<html><h1>ok</h1></html>', headers={'Content-Type': media_types.TEXT_HTML})
    elif content_type == 'protobuf':
        return Response('SomeProtobufObject()', headers={'Content-Type': media_types.APPLICATION_PROTOBUF})
    elif content_type == 'xml':
        return Response(etree.tostring(E.response('some xml')), headers={'Content-Type': media_types.APPLICATION_XML})
    elif content_type == 'javascript':
        return Response('document.body.write("Привет")', headers={'Content-Type': media_types.APPLICATION_JAVASCRIPT})
    elif content_type == 'text':
        return Response('привет charset'.encode(), headers={'Content-Type': media_types.TEXT_PLAIN})
    return Response()


class TestDebug(FrontikTestBase):
    def setup_method(self):
        options.debug = True

    def teardown_method(self):
        options.debug = False

    async def test_debug_page(self):
        response = await self.fetch('/debug?debug')
        response_content = to_unicode(response.raw_body)

        assert response.status_code == 200

        # Basic debug messages

        basic_messages = (
            'debug: starting debug page',
            'warning: testing simple inherited debug',
            'error: testing failing urls',
            'info: testing responses',
        )

        for msg in basic_messages:
            assert msg in response_content

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
            assert msg in response_content

        # Check that all http requests are present

        assert response_content.count('<div class="timebar">') == 17

        # Inherited debug

        assert_occurs_twice = (
            'ValueError: Testing an exception',
            '<span class="entry__head__expandtext">Exception traceback</span>',
            '<span class="entry__head__expandtext">testing xml output</span>',
            '<span class="entry__head__expandtext">testing utf-8 text output</span>',
            '<span class="entry__head__expandtext">testing unicode text output</span>',
        )

        for msg in assert_occurs_twice:
            assert response_content.count(msg) == 2

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
            assert msg not in response_content


@router.get('/debug_simple')
async def get_page():
    return Response('ok')


class TestDebugFailed(FrontikTestBase):
    DEBUG_BASIC_AUTH = create_basic_auth_header('user:god')

    def setup_method(self):
        options.debug_login = 'user'
        options.debug_password = 'god'

    def teardown_method(self):
        options.debug_login = None
        options.debug_password = None

    async def assert_debug_response_code(
        self,
        page: str,
        expected_code: int,
        headers: Optional[dict[str, str]] = None,
    ) -> RequestResult:
        response = await self.fetch(page, headers=headers)
        assert response.status_code == expected_code
        return response

    async def test_debug_by_basic_auth(self):
        for param in ('debug', 'noxsl', 'notpl'):
            response = await self.assert_debug_response_code(f'/debug_simple?{param}', http.client.UNAUTHORIZED)
            assert 'Www-Authenticate' in response.headers
            assert re.match('Basic realm="[^"]+"', response.headers['Www-Authenticate'])

            await self.assert_debug_response_code(
                f'/debug_simple?{param}',
                http.client.OK,
                headers={'Authorization': self.DEBUG_BASIC_AUTH},
            )

    async def test_debug_by_basic_auth_with_invalid_header(self) -> None:
        invalid_headers = (
            'Token user:god',
            'Bearer abcdfe0123456789',
            'Basic',
            'Basic ',
            'Basic ScrewYou',
            create_basic_auth_header(':'),
            create_basic_auth_header(''),
            create_basic_auth_header('not:pass'),
            'BASIC {}'.format(to_unicode(base64.b64encode(b'user:god'))),
        )

        for h in invalid_headers:
            await self.assert_debug_response_code(
                '/debug_simple?debug', http.client.UNAUTHORIZED, headers={'Authorization': h}
            )

    async def test_debug_by_header(self):
        for param in ('debug', 'noxsl', 'notpl'):
            response = await self.assert_debug_response_code(f'/debug_simple?{param}', http.client.UNAUTHORIZED)

            assert 'Www-Authenticate' in response.headers
            assert 'Basic realm="Secure Area"' == response.headers['Www-Authenticate']

            await self.assert_debug_response_code(
                f'/debug_simple?{param}',
                http.client.OK,
                headers={'Frontik-Debug-Auth': 'user:god'},
            )

            await self.assert_debug_response_code(
                f'/debug_simple?{param}',
                http.client.OK,
                headers={'Frontik-Debug-Auth': 'user:god', 'Authorization': 'Basic bad'},
            )

    async def test_debug_by_header_with_wrong_header(self) -> None:
        for value in ('', 'not:pass', 'user: god', self.DEBUG_BASIC_AUTH):
            response = await self.assert_debug_response_code(
                '/debug_simple?debug',
                http.client.UNAUTHORIZED,
                headers={'Frontik-Debug-Auth': value},
            )

            assert 'Www-Authenticate' in response.headers
            assert 'Frontik-Debug-Auth-Header realm="Secure Area"' == response.headers['Www-Authenticate']

    async def test_debug_by_cookie(self):
        for param in ('debug', 'noxsl', 'notpl'):
            await self.assert_debug_response_code(
                '/debug_simple', http.client.UNAUTHORIZED, headers={'Cookie': f'{param}=true'}
            )

            await self.assert_debug_response_code(
                '/debug_simple',
                http.client.OK,
                headers={'Cookie': f'{param}=true;', 'Authorization': self.DEBUG_BASIC_AUTH},
            )

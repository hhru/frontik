import json

from lxml import etree
from tornado.escape import utf8
from tornado.httpclient import AsyncHTTPClient
from tornado.testing import AsyncHTTPTestCase
from tornado_mock.httpclient import patch_http_client, safe_template

# noinspection PyUnresolvedReferences
import frontik.options
from frontik.util import make_url
import aiohttp
import asyncio
from frontik.server import FrontikServer
from aioresponses import aioresponses
import pytest




# def start_frontik_server(self, config_path):
#     loop = asyncio.get_event_loop()
#     self.frontik_server = FrontikServer(config_path)
#     loop.create_task(self.frontik_server.run())
#
# def teardown_method(self):
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(self.frontik_server.server_stop())

# def get_port(self):
#     ports = set()
#     for fd, sock in self.frontik_server.http_server._sockets.items():
#         ports.add(sock.getsockname()[1])
#
#     if len(ports) != 1:
#         raise RuntimeError("can't get frontik port")
#
#     return ports.pop()


class FrontikTestBase:
    # def setup_method(self):
    #     print('-----------setup_method-FrontikTestBase---------')
    #     # FrontikTestBase.ooouu_my

    @pytest.fixture(scope="function", autouse=True)
    def ooouu_my(self, set_stub22390):
        print('----------FrontikTestBase-ooouu_my-fixtura-set-self-setup--------')
        self.set_stub223 = set_stub22390
        return set_stub22390

    async def fetch(self, path, query=None, **kwargs) -> aiohttp.ClientResponse:
        pass

    async def fetch_xml(self, path, query=None, **kwargs):
        pass

    async def fetch_json(self, path, query=None, **kwargs):
        pass

    def set_stub(self, url,
                 response_function=None, response_file=None, response_body='',
                 response_code=200, response_headers=None,
                 response_body_processor=safe_template, **kwargs):

        self.set_stub223.mock(
            url,
            response_file=response_file, response_function=response_function, response_body=response_body,
            response_code=response_code, response_headers=response_headers,
            response_body_processor=response_body_processor,
            **kwargs
        )














# import json
#
# from lxml import etree
# from tornado.escape import utf8
# from tornado.httpclient import AsyncHTTPClient
# from tornado.testing import AsyncHTTPTestCase
# from tornado_mock.httpclient import patch_http_client, safe_template, set_stub
#
# # noinspection PyUnresolvedReferences
# import frontik.options
# from frontik.util import make_url
#
#
# class FrontikTestCase(AsyncHTTPTestCase):
#     """Adds several convenient methods to `tornado.testing.AsyncHTTPTestCase`."""
#
#     def get_http_client(self):
#         """Overrides `AsyncHTTPTestCase.get_http_client` to separate unit test HTTPClient
#         from application HTTPClient.
#
#         This allows mocking HTTP requests made by application in unit tests.
#         """
#         AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
#         return AsyncHTTPClient(force_instance=True)
#
#     async def fetch(self, path, query=None, **kwargs):
#         """Extends `AsyncHTTPTestCase.fetch` method with `query` kwarg.
#         This argument accepts a `dict` of request query parameters that will be encoded
#         and added to request path.
#         Any additional kwargs will be passed to `AsyncHTTPTestCase.fetch`.
#         """
#         query = {} if query is None else query
#         return super().fetch(make_url(path, **query), **kwargs)
#
#     async def fetch_xml(self, path, query=None, **kwargs):
#         """Fetch the request and parse xml document from response body."""
#         resp = await self.fetch(path, query, **kwargs)
#         return etree.fromstring(utf8(resp.body))
#
#     async def fetch_json(self, path, query=None, **kwargs):
#         """Fetch the request and parse JSON tree from response body."""
#         resp = await self.fetch(path, query, **kwargs)
#         return json.loads(resp.body)
#
#     def patch_app_http_client(self, app):
#         """Patches application HTTPClient to enable requests stubbing."""
#         # patch_http_client(app.tornado_http_client)
#         pass
#
#     def set_stub(self, url, request_method='GET',
#                  response_function=None, response_file=None, response_body='',
#                  response_code=200, response_headers=None,
#                  response_body_processor=safe_template, **kwargs):
#
#         # set_stub(
#         #     self._app.tornado_http_client, url, request_method,
#         #     response_function, response_file, response_body, response_code, response_headers,
#         #     response_body_processor, **kwargs
#         # )
#         pass
#
#     def tearDown(self) -> None:
#         super().tearDown()
#
#     def configure_app(self, **kwargs):
#         """Updates or adds options to application config."""
#         for name, val in kwargs.items():
#             setattr(self._app.config, name, val)
#
#         return self











import pytest
from aioresponses import aioresponses

from frontik.util import safe_template


@pytest.fixture
def mock_client():
    with aioresponses() as m:
        yield m


def to_unicode(value) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, bytes):
        raise TypeError("Expected bytes, unicode, or None; got %r" % type(value))
    return value.decode("utf-8")


def _get_stub(path):
    with open(path, 'rb') as f:
        return f.read()


def _guess_headers(fileName):
    if fileName.endswith('.json'):
        return {'Content-Type': 'application/json'}
    if fileName.endswith('.xml'):
        return {'Content-Type': 'application/xml'}
    if fileName.endswith('.txt'):
        return {'Content-Type': 'text/plain'}
    if fileName.endswith('.proto'):
        return {'Content-Type': 'application/x-protobuf'}
    return {}

import re

class MyTester:
    def __init__(self, mock_client):
        self.mock_client = mock_client

    def mock(self, url, request_method='GET',
             response_function=None, response_file=None, response_body='',
             response_code=200, response_headers=None,
             response_body_processor=safe_template, **kwargs):

        if not isinstance(url, re.Pattern):
            url = safe_template(url, **kwargs)

        if response_file is not None:
            headers = _guess_headers(response_file)
            content = _get_stub(response_file)
        else:
            headers = {}
            content = response_body

        if callable(response_body_processor):
            content = response_body_processor(content, **kwargs)

        if response_headers is not None:
            headers.update(response_headers)

        if response_function is not None:
            raise NotImplemented('vam vot realno eto nado?')

        self.mock_client.add(url, method=request_method, status=response_code, headers=headers, body=content, repeat=True)


@pytest.fixture
def set_stub22390(mock_client):
    return MyTester(mock_client)


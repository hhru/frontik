from lxml import etree
from tornado.escape import json_decode, utf8
from tornado.httpclient import AsyncHTTPClient
from tornado.testing import AsyncHTTPTestCase
from tornado_mock.httpclient import patch_http_client, safe_template, set_stub

# noinspection PyUnresolvedReferences
import frontik.options
from frontik.util import make_url


class FrontikTestCase(AsyncHTTPTestCase):
    """Adds several convenient methods to `tornado.testing.AsyncHTTPTestCase`."""

    def get_http_client(self):
        """Overrides `AsyncHTTPTestCase.get_http_client` to separate unit test HTTPClient
        from application HTTPClient.

        This allows mocking HTTP requests made by application in unit tests.
        """
        AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
        return AsyncHTTPClient(force_instance=True)

    def fetch(self, path, query=None, **kwargs):
        """Extends `AsyncHTTPTestCase.fetch` method with `query` kwarg.
        This argument accepts a `dict` of request query parameters that will be encoded
        and added to request path.
        Any additional kwargs will be passed to `AsyncHTTPTestCase.fetch`.
        """
        query = {} if query is None else query
        return super().fetch(make_url(path, **query), **kwargs)

    def fetch_xml(self, path, query=None, **kwargs):
        """Fetch the request and parse xml document from response body."""
        return etree.fromstring(utf8(self.fetch(path, query, **kwargs).body))

    def fetch_json(self, path, query=None, **kwargs):
        """Fetch the request and parse JSON tree from response body."""
        return json_decode(self.fetch(path, query, **kwargs).body)

    def patch_app_http_client(self, app):
        """Patches application HTTPClient to enable requests stubbing."""
        patch_http_client(app.http_client_factory.tornado_http_client)

    def set_stub(self, url, request_method='GET',
                 response_function=None, response_file=None, response_body='',
                 response_code=200, response_headers=None,
                 response_body_processor=safe_template, **kwargs):

        set_stub(
            self._app.http_client_factory.tornado_http_client, url, request_method,
            response_function, response_file, response_body, response_code, response_headers,
            response_body_processor, **kwargs
        )

    def configure_app(self, **kwargs):
        """Updates or adds options to application config."""
        for name, val in kwargs.items():
            setattr(self._app.config, name, val)

        return self

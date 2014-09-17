from collections import namedtuple

from frontik.handler import BaseHandler
from frontik.http_client import HttpClient


class MicroHandler(BaseHandler):

    _Request = namedtuple('_Request', ('host', 'uri', 'kwargs'))

    class GET(_Request):
        __slots__ = ()

        def __new__(cls, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
                    follow_redirects=True, labels=None):
            return super(MicroHandler.GET, cls).__new__(
                cls, host, uri, dict(
                    data=data, headers=headers,
                    connect_timeout=connect_timeout, request_timeout=request_timeout,
                    follow_redirects=follow_redirects, labels=labels,
                    parse_on_error=True
                )
            )

    class POST(_Request):
        __slots__ = ()

        def __new__(cls, host, uri, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
                    follow_redirects=True, content_type=None, labels=None):
            return super(MicroHandler.POST, cls).__new__(
                cls, host, uri, dict(
                    data=data, headers=headers, files=files,
                    connect_timeout=connect_timeout, request_timeout=request_timeout,
                    follow_redirects=follow_redirects, content_type=content_type, labels=labels,
                    parse_on_error=True
                )
            )

    class PUT(_Request):
        __slots__ = ()

        def __new__(cls, host, uri, data='', headers=None, connect_timeout=None, request_timeout=None,
                    content_type=None, labels=None):
            return super(MicroHandler.PUT, cls).__new__(
                cls, host, uri, dict(
                    data=data, headers=headers,
                    connect_timeout=connect_timeout, request_timeout=request_timeout,
                    content_type=content_type, labels=labels,
                    parse_on_error=True
                )
            )

    class DELETE(_Request):
        __slots__ = ()

        def __new__(cls, host, uri, data='', headers=None, connect_timeout=None, request_timeout=None,
                    content_type=None, labels=None):
            return super(MicroHandler.DELETE, cls).__new__(
                cls, host, uri, dict(
                    data=data, headers=headers,
                    connect_timeout=connect_timeout, request_timeout=request_timeout,
                    content_type=content_type, labels=labels,
                    parse_on_error=True
                )
            )

    def __init__(self, application, request, logger, request_id=None, app_globals=None, **kwargs):
        super(MicroHandler, self).__init__(application, request, logger, request_id, app_globals, **kwargs)

        def fetcher_wrapper(*args, **kwargs):
            return self._http_client.fetch_request(*args, **kwargs)

        self._http_client = HttpClient(self, self._app_globals.curl_http_client, fetcher_wrapper)

        self._METHODS_MAPPING = {
            MicroHandler.GET: self._http_client.get_url,
            MicroHandler.POST: self._http_client.post_url,
            MicroHandler.PUT: self._http_client.put_url,
            MicroHandler.DELETE: self._http_client.delete_url
        }

    def _wrap_method(self, handler_method):
        done_method_name = handler_method.__name__ + '_requests_done'

        def _inner():
            result = handler_method()
            if isinstance(result, dict):
                def _callback(data):
                    if hasattr(self, done_method_name):
                        getattr(self, done_method_name)(data)

                futures = {}
                for name, req in result.iteritems():
                    req_type = type(req)
                    if req_type not in self._METHODS_MAPPING:
                        raise Exception('Unexpected HTTP method of type {}'.format(req_type))

                    method = self._METHODS_MAPPING[req_type]
                    url = req.host + (req.uri if req.uri.startswith('/') else '/' + req.uri)
                    futures[name] = method(url, **req.kwargs)

                self._http_client.group(futures, _callback)

        return _inner

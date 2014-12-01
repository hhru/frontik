from collections import namedtuple
from functools import partial

from frontik.handler import BaseHandler, HTTPError


class MicroHandler(BaseHandler):

    _Request = namedtuple('_Request', ('method', 'host', 'uri', 'kwargs'))

    def GET(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
            follow_redirects=True, labels=None, fail_on_error=False):
        return MicroHandler._Request(
            'GET', host, uri, dict(
                data=data, headers=headers,
                connect_timeout=connect_timeout, request_timeout=request_timeout,
                follow_redirects=follow_redirects, labels=labels,
                parse_on_error=True, fail_on_error=fail_on_error
            )
        )

    def POST(self, host, uri, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
             follow_redirects=True, content_type=None, labels=None, fail_on_error=False):
        return MicroHandler._Request(
            'POST', host, uri, dict(
                data=data, headers=headers, files=files,
                connect_timeout=connect_timeout, request_timeout=request_timeout,
                follow_redirects=follow_redirects, content_type=content_type, labels=labels,
                parse_on_error=True, fail_on_error=fail_on_error
            )
        )

    def PUT(self, host, uri, data='', headers=None, connect_timeout=None, request_timeout=None,
            content_type=None, labels=None, fail_on_error=False):
        return MicroHandler._Request(
            'PUT', host, uri, dict(
                data=data, headers=headers,
                connect_timeout=connect_timeout, request_timeout=request_timeout,
                content_type=content_type, labels=labels,
                parse_on_error=True, fail_on_error=fail_on_error
            )
        )

    def DELETE(self, host, uri, data='', headers=None, connect_timeout=None, request_timeout=None,
               content_type=None, labels=None, fail_on_error=False):
        return MicroHandler._Request(
            'DELETE', host, uri, dict(
                data=data, headers=headers,
                connect_timeout=connect_timeout, request_timeout=request_timeout,
                content_type=content_type, labels=labels,
                parse_on_error=True, fail_on_error=fail_on_error
            )
        )

    def __init__(self, application, request, logger, request_id=None, app_globals=None, **kwargs):
        super(MicroHandler, self).__init__(application, request, logger, request_id, app_globals, **kwargs)

        self._METHODS_MAPPING = {
            'GET': self._http_client.get_url,
            'POST': self._http_client.post_url,
            'PUT': self._http_client.put_url,
            'DELETE': self._http_client.delete_url
        }

    def handle_return_value(self, handler_method_name, return_value):
        def _fail_on_error_wrapper(name, data, response):
            error_method_name = handler_method_name + '_requests_failed'
            if hasattr(self, error_method_name):
                getattr(self, error_method_name)(name, data, response)

            status_code = response.code if 300 <= response.code < 500 else 503
            raise HTTPError(status_code, 'HTTP request failed with code {}'.format(response.code))

        if isinstance(return_value, dict):
            futures = {}
            for name, req in return_value.iteritems():
                req_type = getattr(req, 'method', None)
                if req_type not in self._METHODS_MAPPING:
                    raise Exception('Invalid request object: {!r}'.format(req))

                if req.kwargs.pop('fail_on_error'):
                    req.kwargs['error_callback'] = partial(_fail_on_error_wrapper, name)

                method = self._METHODS_MAPPING[req_type]
                url = '{}/{}'.format(req.host.rstrip('/'), req.uri.lstrip('/'))
                futures[name] = method(url, **req.kwargs)

            done_method_name = handler_method_name + '_requests_done'
            self._http_client.group(futures, getattr(self, done_method_name, None), name='MicroHandler')

        elif return_value is not None:
            raise Exception('Invalid return type: {}'.format(type(return_value)))

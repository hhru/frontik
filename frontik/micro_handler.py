# coding=utf-8

from collections import namedtuple
from functools import partial

from tornado.concurrent import Future
from tornado.web import HTTPError

from frontik.handler import BaseHandler
from frontik.http_client import RequestResult


class MicroHandler(BaseHandler):
    _Request = namedtuple('_Request', ('method', 'host', 'uri', 'kwargs'))

    def GET(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
            max_timeout_tries=None, follow_redirects=True, fail_on_error=False):
        future = self._http_client.get_url(
            host, uri,
            data=data, headers=headers,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries,
            follow_redirects=follow_redirects, parse_on_error=True
        )
        future.fail_on_error = fail_on_error
        return future

    def POST(self, host, uri, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
             max_timeout_tries=None, idempotent=False, follow_redirects=True, content_type=None, fail_on_error=False):
        future = self._http_client.post_url(
            host, uri,
            data=data, headers=headers, files=files,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, idempotent=idempotent,
            follow_redirects=follow_redirects, content_type=content_type,
            parse_on_error=True
        )
        future.fail_on_error = fail_on_error
        return future

    def PUT(self, host, uri, data='', headers=None, connect_timeout=None, request_timeout=None,
            max_timeout_tries=None, content_type=None, fail_on_error=False):
        future = self._http_client.put_url(
            host, uri,
            data=data, headers=headers,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries,
            content_type=content_type,
            parse_on_error=True
        )
        future.fail_on_error = fail_on_error
        return future

    def DELETE(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
               max_timeout_tries=None, content_type=None, fail_on_error=False):
        future = self._http_client.delete_url(
            host, uri,
            data=data, headers=headers,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries,
            content_type=content_type,
            parse_on_error=True
        )
        future.fail_on_error = fail_on_error
        return future

    def handle_return_value(self, handler_method_name, return_value):
        def _future_fail_on_error_handler(name, future):
            result = future.result()
            if not isinstance(result, RequestResult):
                return

            if not result.response.error and not result.exception:
                return

            error_method_name = handler_method_name + '_requests_failed'
            if hasattr(self, error_method_name):
                getattr(self, error_method_name)(name, result.data, result.response)

            status_code = result.response.code if 300 <= result.response.code < 500 else 502
            raise HTTPError(status_code, 'HTTP request failed with code {}'.format(result.response.code))

        if isinstance(return_value, dict):
            futures = {}
            for name, future in return_value.items():
                # Use is_future with Tornado 4
                if not isinstance(future, Future):
                    raise Exception('Invalid MicroHandler return value: {!r}'.format(future))

                if getattr(future, 'fail_on_error', False):
                    self.add_future(future, self.finish_group.add(partial(_future_fail_on_error_handler, name)))

                futures[name] = future

            done_method_name = handler_method_name + '_requests_done'
            self._http_client.group(futures, getattr(self, done_method_name, None), name='MicroHandler')

        elif return_value is not None:
            raise Exception('Invalid return type: {}'.format(type(return_value)))

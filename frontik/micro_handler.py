# coding=utf-8

from collections import namedtuple

from frontik.handler import BaseHandler


class MicroHandler(BaseHandler):
    _Request = namedtuple('_Request', ('method', 'host', 'uri', 'kwargs'))

    @staticmethod
    def make_url(host, uri):
        return u'{}/{}'.format(host.rstrip(u'/'), uri.lstrip(u'/'))

    def GET(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
            follow_redirects=True, labels=None, fail_on_error=False):
        future = self._http_client.get_url(
            self.make_url(host, uri),
            data=data, headers=headers,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            follow_redirects=follow_redirects, labels=labels,
            parse_on_error=True
        )
        future.fail_on_error = fail_on_error
        return future

    def POST(self, host, uri, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
             follow_redirects=True, content_type=None, labels=None, fail_on_error=False):

        future = self._http_client.post_url(
            self.make_url(host, uri),
            data=data, headers=headers, files=files,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            follow_redirects=follow_redirects, content_type=content_type, labels=labels,
            parse_on_error=True
        )
        future.fail_on_error = fail_on_error
        return future

    def PUT(self, host, uri, data='', headers=None, connect_timeout=None, request_timeout=None,
            content_type=None, labels=None, fail_on_error=False):
        future = self._http_client.put_url(
            self.make_url(host, uri),
            data=data, headers=headers,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            content_type=content_type, labels=labels,
            parse_on_error=True
        )
        future.fail_on_error = fail_on_error
        return future

    def DELETE(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
               content_type=None, labels=None, fail_on_error=False):
        future = self._http_client.delete_url(
            self.make_url(host, uri),
            data=data, headers=headers,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            content_type=content_type, labels=labels,
            parse_on_error=True
        )
        future.fail_on_error = fail_on_error
        return future

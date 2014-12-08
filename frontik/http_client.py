# coding=utf-8

from collections import namedtuple
from functools import partial
import re

from lxml import etree
import simplejson as json
from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from tornado.options import options

from frontik.async import AsyncGroup
from frontik import frontik_logging
from frontik.globals import global_stats
from frontik.handler_debug import PageHandlerDebug, response_from_debug
import frontik.util


class HttpClient(object):
    def __init__(self, handler, http_client_impl, modify_http_request_hook):
        self.handler = handler
        self.modify_http_request_hook = modify_http_request_hook
        self.http_client_impl = http_client_impl

    def group(self, futures, callback=None, name=None):
        if callable(callback):
            results_holder = {}
            group_callback = self.handler.finish_group.add(partial(callback, results_holder))

            def delay_cb():
                IOLoop.instance().add_callback(self.handler.check_finished(group_callback))

            async_group = AsyncGroup(delay_cb, log=self.handler.log.debug, name=name)

            def callback(future_name, future):
                results_holder[future_name] = future.result()

            for name, future in futures.iteritems():
                future.add_done_callback(async_group.add(partial(callback, name)))

            async_group.try_finish()

        return futures

    def get_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None,
                callback=None, error_callback=None, follow_redirects=True, labels=None,
                add_to_finish_group=True, parse_response=True, parse_on_error=False):

        future = Future()
        request = frontik.util.make_get_request(url, data, headers, connect_timeout, request_timeout, follow_redirects)
        request._frontik_labels = labels

        self.fetch(
            request,
            partial(self._parse_response, future, callback, error_callback, parse_response, parse_on_error),
            add_to_finish_group=add_to_finish_group
        )

        return future

    def post_url(self, url, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
                 callback=None, error_callback=None, follow_redirects=True, content_type=None, labels=None,
                 add_to_finish_group=True, parse_response=True, parse_on_error=False):

        future = Future()
        request = frontik.util.make_post_request(
            url, data, headers, files, content_type, connect_timeout, request_timeout, follow_redirects
        )
        request._frontik_labels = labels

        self.fetch(
            request,
            partial(self._parse_response, future, callback, error_callback, parse_response, parse_on_error),
            add_to_finish_group=add_to_finish_group
        )

        return future

    def put_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None,
                callback=None, error_callback=None, content_type=None, labels=None,
                add_to_finish_group=True, parse_response=True, parse_on_error=False):

        future = Future()
        request = frontik.util.make_put_request(url, data, headers, content_type, connect_timeout, request_timeout)
        request._frontik_labels = labels

        self.fetch(
            request,
            partial(self._parse_response, future, callback, error_callback, parse_response, parse_on_error),
            add_to_finish_group=add_to_finish_group
        )

        return future

    def delete_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None,
                   callback=None, error_callback=None, content_type=None, labels=None,
                   add_to_finish_group=True, parse_response=True, parse_on_error=False):

        future = Future()
        request = frontik.util.make_delete_request(url, data, headers, content_type, connect_timeout, request_timeout)
        request._frontik_labels = labels

        self.fetch(
            request,
            partial(self._parse_response, future, callback, error_callback, parse_response, parse_on_error),
            add_to_finish_group=add_to_finish_group
        )

        return future

    def fetch(self, request, callback, add_to_finish_group=True):
        """ Tornado HTTP client compatible method """
        if not self.handler._finished:
            global_stats.http_reqs_count += 1

            if self.handler._prepared and self.handler.debug.debug_mode.pass_debug:
                authorization = self.handler.request.headers.get('Authorization')
                request.headers[PageHandlerDebug.DEBUG_HEADER_NAME] = True
                if authorization is not None:
                    request.headers['Authorization'] = authorization

            request.headers['X-Request-Id'] = self.handler.request_id

            if request.connect_timeout is None:
                request.connect_timeout = options.http_client_default_connect_timeout
            if request.request_timeout is None:
                request.request_timeout = options.http_client_default_request_timeout

            request.connect_timeout *= options.timeout_multiplier
            request.request_timeout *= options.timeout_multiplier

            if add_to_finish_group:
                req_callback = self.handler.finish_group.add(
                    self.handler.check_finished(self._log_response, request, callback)
                )
            else:
                req_callback = partial(self._log_response, request, callback)

            return self.http_client_impl.fetch(self.modify_http_request_hook(request), req_callback)

        self.handler.log.warning('attempted to make http request to %s when page is finished, ignoring', request.url)

    def _log_response(self, request, callback, response):
        try:
            if response.body is not None:
                global_stats.http_reqs_size_sum += len(response.body)
        except TypeError:
            self.handler.log.warning('got strange response.body of type %s', type(response.body))

        try:
            debug_extra = {}
            if response.headers.get(PageHandlerDebug.DEBUG_HEADER_NAME):
                debug_response = response_from_debug(request, response)
                if debug_response is not None:
                    debug_xml, response = debug_response
                    debug_extra['_debug_response'] = debug_xml

            debug_extra.update({'_response': response, '_request': request})
            if getattr(request, '_frontik_labels', None) is not None:
                debug_extra['_labels'] = request._frontik_labels

            self.handler.log.info(
                'got {code}{size} {url} in {time:.2f}ms'.format(
                    code=response.code,
                    url=response.effective_url,
                    size=' {0} bytes'.format(len(response.body)) if response.body is not None else '',
                    time=response.request_time * 1000
                ),
                extra=debug_extra
            )
        except Exception:
            self.handler.log.exception('Cannot log response info')

        if callable(callback):
            callback(response)

    def _parse_response(self, future, callback, error_callback, parse_response, parse_on_error, response):
        data = None
        result = RequestResult()

        try:
            if response.error and not parse_on_error:
                self._set_response_error(response)
            elif not parse_response:
                data = response.body
            elif response.code != 204:
                content_type = response.headers.get('Content-Type', '')
                for k, v in DEFAULT_REQUEST_TYPES.iteritems():
                    if k.search(content_type):
                        data = v(response, logger=self.handler.log)
                        break
        except FailedRequestException as ex:
            result.set_exception(ex)

        if callable(error_callback) and (response.error or result.exception is not None):
            error_callback(data, response)
        elif callable(callback):
            callback(data, response)

        result.set(data, response)
        future.set_result(result)

    def _set_response_error(self, response):
        log_func = self.handler.log.error if response.code >= 500 else self.handler.log.warning
        log_func('{code} failed {url} ({reason!s})'.format(
            code=response.code, url=response.effective_url, reason=response.error)
        )

        raise FailedRequestException(reason=str(response.error), code=response.code)


class FailedRequestException(Exception):
    def __init__(self, **kwargs):
        self.attrs = kwargs


class RequestResult(object):
    __slots__ = ('data', 'response', 'exception')

    ResponseData = namedtuple('ResponseData', ('data', 'response'))

    def __init__(self):
        self.data = None
        self.response = None
        self.exception = None

    def set(self, data, response):
        self.data = data
        self.response = response

    def get(self):
        return RequestResult.ResponseData(self.data, self.response)

    def set_exception(self, exception):
        self.exception = exception


def _parse_response(response, logger=frontik_logging.log, parser=None, response_type=None):
    try:
        return parser(response.body)
    except:
        _preview_len = 100

        if len(response.body) > _preview_len:
            body_preview = '{0}...'.format(response.body[:_preview_len])
        else:
            body_preview = response.body

        logger.exception('failed to parse {0} response from {1}, bad data: "{2}"'.format(
            response_type, response.effective_url, body_preview))

        raise FailedRequestException(url=response.effective_url, reason='invalid {0}'.format(response_type))


_xml_parser = etree.XMLParser(strip_cdata=False)
_parse_response_xml = partial(_parse_response,
                              parser=lambda x: etree.fromstring(x, parser=_xml_parser),
                              response_type='XML')

_parse_response_json = partial(_parse_response,
                               parser=json.loads,
                               response_type='JSON')

DEFAULT_REQUEST_TYPES = {
    re.compile('.*xml.?'): _parse_response_xml,
    re.compile('.*json.?'): _parse_response_json,
    re.compile('.*text/plain.?'): (lambda response, logger: response.body),
}

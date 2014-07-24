# coding=utf-8

import base64
import httplib
import time
from functools import partial

import tornado.options
import tornado.web
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPRequest

from frontik.async import AsyncGroup
import frontik.auth
from frontik.frontik_logging import PageLogger
from frontik.future import Future
from frontik.globals import global_stats
import frontik.handler_active_limit
from frontik.handler_debug import PageHandlerDebug, response_from_debug
import frontik.util
import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik.responses import DEFAULT_REQUEST_TYPES, FailedRequestException, RequestResult


# this function replaces __repr__ function for tornado's HTTPRequest
# the difference is in handling body attribute: values of various `password` fields in POST requests
# are replaced with '***' to secure them from showing up in the logs
def context_based_repr(self):
    attrs = ("protocol", "host", "method", "uri", "version", "remote_ip")
    if tornado.options.options.debug:
        attrs += ("body",)

    args = ", ".join(["%s=%r" % (n, getattr(self, n)) for n in attrs])
    return "%s(%s, headers=%s)" % (
        self.__class__.__name__, args, dict(self.headers))


HTTPRequest.__repr__ = context_based_repr


class HTTPError(tornado.web.HTTPError):
    """Extends tornado.web.HTTPError with several keyword-only arguments.

    :arg dict headers: Custom HTTP headers to pass along with the error response.
    :arg string text: Plain text override for error response.
    :arg etree xml: XML node to be added to `self.doc`. If present, error page will be
        produced with `application/xml` content type.
    :arg dict json: JSON dict to be used as error response. If present, error page
        will be produced with `application/json` content type.
    """
    def __init__(self, status_code, log_message=None, *args, **kwargs):
        headers = kwargs.pop('headers', {})
        for data in ('text', 'xml', 'json'):
            setattr(self, data, kwargs.pop(data, None))

        if status_code not in httplib.responses:
            status_code = 503

        super(HTTPError, self).__init__(status_code, log_message, *args, **kwargs)
        self.headers = headers


class PageHandler(tornado.web.RequestHandler):

    preprocessors = ()

    # to restore tornado.web.RequestHandler compatibility
    def __init__(self, application, request, app_globals=None, **kwargs):
        self.handler_started = time.time()
        self._prepared = False

        if app_globals is None:
            raise Exception('{0} need to have app_globals'.format(PageHandler))

        self.name = self.__class__.__name__
        self.request_id = request.headers.get('X-Request-Id', str(global_stats.next_request_id()))
        logger_name = '.'.join(filter(None, [self.request_id, getattr(app_globals.config, 'app_name', None)]))
        self.log = PageLogger(self, logger_name, request.path or request.uri)

        super(PageHandler, self).__init__(application, request, logger=self.log, **kwargs)

        self.app_globals = app_globals
        self.config = self.app_globals.config
        self.http_client = self.app_globals.http_client
        self._debug_access = None

        self._template_postprocessors = []
        self._early_postprocessors = []
        self._late_postprocessors = []

        # this is deprecated
        if hasattr(self.config, 'postprocessor'):
            self.add_template_postprocessor(self.config.postprocessor)

        self.text = None

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def initialize(self, logger=None, **kwargs):
        # Hides logger keyword argument from incompatible tornado versions
        super(PageHandler, self).initialize(**kwargs)

    def prepare(self):
        self.active_limit = frontik.handler_active_limit.PageHandlerActiveLimit(self)
        self.debug = PageHandlerDebug(self)

        self.json_producer = frontik.producers.json_producer.JsonProducer(
            self, self.app_globals.json, getattr(self, 'json_encoder', None))
        self.json = self.json_producer.json

        self.xml_producer = frontik.producers.xml_producer.XmlProducer(self, self.app_globals.xml)
        self.xml = self.xml_producer  # deprecated synonym
        self.doc = self.xml_producer.doc

        if self.get_argument('nopost', None) is not None:
            self.require_debug_access()
            self.apply_postprocessor = False
            self.log.debug('apply_postprocessor = False due to "nopost" argument')
        else:
            self.apply_postprocessor = True

        if tornado.options.options.long_request_timeout:
            # add long requests timeout
            self.finish_timeout_handle = IOLoop.instance().add_timeout(
                time.time() + tornado.options.options.long_request_timeout, self.__handle_long_request)

        self.finish_group = AsyncGroup(self.check_finished(self._finish_page_cb), name='finish', log=self.log.debug)
        self._prepared = True

    def require_debug_access(self, login=None, passwd=None):
        if self._debug_access is None:
            if tornado.options.options.debug:
                self._debug_access = True
            else:
                check_login = login if login is not None else tornado.options.options.debug_login
                check_passwd = passwd if passwd is not None else tornado.options.options.debug_password

                self._debug_access = frontik.auth.passed_basic_auth(self, check_login, check_passwd)

            if not self._debug_access:
                raise HTTPError(401, headers={'WWW-Authenticate': 'Basic realm="Secure Area"'})

    def decode_argument(self, value, name=None):
        try:
            return super(PageHandler, self).decode_argument(value, name)
        except (UnicodeError, tornado.web.HTTPError):
            self.log.warn('Cannot decode utf-8 query parameter, trying other charsets')

        try:
            return frontik.util.decode_string_from_charset(value)
        except UnicodeError:
            self.log.exception('Cannot decode argument, ignoring invalid chars')
            return value.decode('utf-8', 'ignore')

    def check_finished(self, callback, *args, **kwargs):
        original_callback = callback
        if args or kwargs:
            callback = partial(callback, *args, **kwargs)

        def wrapper(*args, **kwargs):
            if self._finished:
                self.log.warn('Page was already finished, {0} ignored'.format(original_callback))
            else:
                callback(*args, **kwargs)

        return wrapper

    def set_status(self, status_code):
        if status_code not in httplib.responses:
            status_code = 503
        super(PageHandler, self).set_status(status_code)

    @staticmethod
    def add_callback(callback):
        IOLoop.instance().add_callback(callback)

    @staticmethod
    def add_timeout(deadline, callback):
        IOLoop.instance().add_timeout(deadline, callback)

    # Requests handling

    @tornado.web.asynchronous
    def post(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, self._wrap_method(self.post_page))
        self._finish_page()

    @tornado.web.asynchronous
    def get(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, self._wrap_method(self.get_page))
        self._finish_page()

    @tornado.web.asynchronous
    def head(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, self._wrap_method(self.get_page))
        self._finish_page()

    @tornado.web.asynchronous
    def delete(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, self._wrap_method(self.delete_page))
        self._finish_page()

    @tornado.web.asynchronous
    def put(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, self._wrap_method(self.put_page))
        self._finish_page()

    def options(self, *args, **kwargs):
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def _wrap_method(self, handler_method):
        return handler_method

    def get_page(self):
        """ This method can be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def post_page(self):
        """ This method can be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def put_page(self):
        """ This method can be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def delete_page(self):
        """ This method can be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def __get_allowed_methods(self):
        return [name for name in ('get', 'post', 'put', 'delete') if '{0}_page'.format(name) in vars(self.__class__)]

    # HTTP client methods

    DEFAULT_CONNECT_TIMEOUT = 0.2
    DEFAULT_REQUEST_TIMEOUT = 2

    def group(self, futures, callback=None, name=None):
        if callable(callback):
            results_holder = {}
            group_callback = self.finish_group.add(partial(callback, results_holder))

            def delay_cb():
                IOLoop.instance().add_callback(self.check_finished(group_callback))

            async_group = AsyncGroup(delay_cb, log=self.log.debug, name=name)

            def callback(future_name, future):
                results_holder[future_name] = future.result().get()

            for name, future in futures.iteritems():
                future.add_done_callback(async_group.add(partial(callback, name)))

            async_group.try_finish()

        return futures

    def get_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None, callback=None,
                follow_redirects=True, labels=None, add_to_finish_group=True, **params):

        future = Future()
        request = frontik.util.make_get_request(url, data, headers, connect_timeout, request_timeout, follow_redirects)
        request._frontik_labels = labels

        self.fetch_request(request, partial(self._parse_response, future, callback, **params),
                           add_to_finish_group=add_to_finish_group)

        return future

    def post_url(self, url, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
                 callback=None, follow_redirects=True, content_type=None, labels=None,
                 add_to_finish_group=True, **params):

        future = Future()
        request = frontik.util.make_post_request(
            url, data, headers, files, content_type, connect_timeout, request_timeout, follow_redirects
        )
        request._frontik_labels = labels

        self.fetch_request(request, partial(self._parse_response, future, callback, **params),
                           add_to_finish_group=add_to_finish_group)

        return future

    def put_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None, callback=None,
                content_type=None, labels=None, add_to_finish_group=True, **params):

        future = Future()
        request = frontik.util.make_put_request(url, data, headers, content_type, connect_timeout, request_timeout)
        request._frontik_labels = labels

        self.fetch_request(request, partial(self._parse_response, future, callback, **params),
                           add_to_finish_group=add_to_finish_group)

        return future

    def delete_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None, callback=None,
                   content_type=None, labels=None, add_to_finish_group=True, **params):

        future = Future()
        request = frontik.util.make_delete_request(url, data, headers, content_type, connect_timeout, request_timeout)
        request._frontik_labels = labels

        self.fetch_request(request, partial(self._parse_response, future, callback, **params),
                           add_to_finish_group=add_to_finish_group)

        return future

    def fetch_request(self, request, callback, add_to_finish_group=True):
        """ Tornado HTTP client compatible method """
        if not self._finished:
            global_stats.http_reqs_count += 1

            if self._prepared and self.debug.debug_mode.pass_debug:
                authorization = self.request.headers.get('Authorization')
                request.headers[PageHandlerDebug.DEBUG_HEADER_NAME] = True
                if authorization is not None:
                    request.headers['Authorization'] = authorization

            request.headers['X-Request-Id'] = self.request_id

            if request.connect_timeout is None:
                request.connect_timeout = self.DEFAULT_CONNECT_TIMEOUT
            if request.request_timeout is None:
                request.request_timeout = self.DEFAULT_REQUEST_TIMEOUT

            request.connect_timeout *= tornado.options.options.timeout_multiplier
            request.request_timeout *= tornado.options.options.timeout_multiplier

            if add_to_finish_group:
                req_callback = self.finish_group.add(self.check_finished(self._log_response, request, callback))
            else:
                req_callback = partial(self._log_response, request, callback)

            return self.http_client.fetch(request, req_callback)

        self.log.warn('attempted to make http request to {0} when page is finished, ignoring'.format(request.url))

    def _log_response(self, request, callback, response):
        try:
            if response.body is not None:
                global_stats.http_reqs_size_sum += len(response.body)
        except TypeError:
            self.log.warn('got strange response.body of type %s', type(response.body))

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

            self.log.debug(
                'got {code}{size} {url} in {time:.2f}ms'.format(
                    code=response.code,
                    url=response.effective_url,
                    size=' {0} bytes'.format(len(response.body)) if response.body is not None else '',
                    time=response.request_time * 1000
                ),
                extra=debug_extra
            )
        except Exception:
            self.log.exception('Cannot log response info')

        if callable(callback):
            callback(response)

    def _parse_response(self, future, callback, response, **params):
        data = None
        result = RequestResult()

        try:
            if response.error and not params.get('parse_on_error', False):
                self._set_response_error(response)
            elif not params.get('parse_response', True):
                data = response.body
            elif response.code != 204:
                content_type = response.headers.get('Content-Type', '')
                for k, v in DEFAULT_REQUEST_TYPES.iteritems():
                    if k.search(content_type):
                        data = v(response, logger=self.log)
                        break
        except FailedRequestException as ex:
            result.set_exception(ex)

        result.set(data, response)

        if callable(callback):
            def callback_wrapper(future):
                callback(*future.result().get())

            future.add_done_callback(callback_wrapper)

        future.set_result(result)

    def _set_response_error(self, response):
        log_func = self.log.error if response.code >= 500 else self.log.warn
        log_func('{code} failed {url} ({reason!s})'.format(
            code=response.code, url=response.effective_url, reason=response.error)
        )

        raise FailedRequestException(reason=str(response.error), code=response.code)

    # Finish page

    def _finish_page(self):
        self.finish_group.try_finish()

    def _force_finish(self):
        self.finish_group.finish()

    def _finish_page_cb(self):
        if not self._finished:
            self.log.stage_tag('page')

            def _callback():
                if self.text is not None:
                    producer = self._generic_producer
                elif not self.json.is_empty():
                    producer = self.json_producer
                else:
                    producer = self.xml_producer

                self.log.debug('Using {0} producer'.format(producer))

                if self.apply_postprocessor:
                    producer(partial(self._call_postprocessors, self._template_postprocessors, self.finish))
                else:
                    producer(self.finish)

            self._call_postprocessors(self._early_postprocessors, _callback)
        else:
            self.log.warn('trying to finish already finished page, probably bug in a workflow, ignoring')

    def __handle_long_request(self):
        self.log.warning("long request detected (uri: {0})".format(self.request.uri))
        if tornado.options.options.kill_long_requests:
            self.send_error()

    def send_error(self, status_code=500, headers=None, **kwargs):
        exception = kwargs.get('exception', None)

        # headers argument is deprecated
        if headers is None:
            headers = getattr(exception, 'headers', None)

        if headers is None:
            headers = {}

        override_content = any(getattr(exception, x, None) is not None for x in ('text', 'xml', 'json'))
        finish_with_exception = exception is not None and (
            199 < status_code < 400 or  # raise HTTPError(200) to finish page immediately
            override_content
        )

        if finish_with_exception or headers:
            self.set_status(status_code)
            for (name, value) in headers.iteritems():
                self.set_header(name, value)

            self.json.clear()

            if getattr(exception, 'text', None) is not None:
                self.doc.clear()
                self.text = exception.text
            elif getattr(exception, 'json', None) is not None:
                self.text = None
                self.doc.clear()
                self.json.put(exception.json)
            elif getattr(exception, 'xml', None) is not None:
                self.text = None
                # cannot clear self.doc due to backwards compatibility, a bug actually
                self.doc.put(exception.xml)

            self._force_finish()
            return

        return super(PageHandler, self).send_error(status_code, **kwargs)

    def finish(self, chunk=None):
        if hasattr(self, 'finish_timeout_handle'):
            IOLoop.instance().remove_timeout(self.finish_timeout_handle)

        def _finish_with_async_hook():
            self.log.stage_tag('postprocess')

            if hasattr(self, 'active_limit'):
                self.active_limit.release()

            super(PageHandler, self).finish(chunk)
            IOLoop.instance().add_timeout(
                time.time() + 0.1,
                partial(self.log.request_finish_hook, self._status_code, self.request.method, self.request.uri)
            )

        try:
            self._call_postprocessors(self._late_postprocessors, _finish_with_async_hook)
        except:
            self.log.exception('Error during late postprocessing stage, finishing with an exception')
            self._status_code = 500
            _finish_with_async_hook()

    def flush(self, include_footers=False, **kwargs):
        self.log.stage_tag('finish')
        self.log.log_stages()

        if self._prepared and (self.debug.debug_mode.enabled or self.debug.debug_mode.error_debug):
            try:
                self._response_size = sum(map(len, self._write_buffer))
                original_headers = {'Content-Length': str(self._response_size)}
                response_headers = dict(self._headers, **original_headers)
                original_response = {
                    'buffer': base64.encodestring(''.join(self._write_buffer)),
                    'headers': response_headers,
                    'code': self._status_code
                }

                res = self.debug.get_debug_page(self._status_code, response_headers, original_response)

                if self.debug.debug_mode.enabled:
                    # change status code only if debug was explicitly requested
                    self._status_code = 200

                if self.debug.debug_mode.inherited:
                    self.set_header(PageHandlerDebug.DEBUG_HEADER_NAME, True)

                self.set_header('Content-disposition', '')
                self.set_header('Content-Length', str(len(res)))
                self._write_buffer = [res]

            except Exception:
                self.log.exception('Cannot write debug info')

        super(PageHandler, self).flush(include_footers=False, **kwargs)

    def _log(self):
        super(PageHandler, self)._log()
        self.log.stage_tag('flush')
        self.log.finish_stages(self._status_code)

    # Preprocessors and postprocessors

    def _call_preprocessors(self, preprocessors, callback):
        self._chain_functions(list(preprocessors), callback)

    def _call_postprocessors(self, postprocessors, callback, *args):
        self._chain_functions(list(postprocessors), callback, *args)

    def _chain_functions(self, functions, callback, *args):
        if functions:
            func = functions.pop(0)
            self.log.debug('Started "%r"', func)
            start_time = time.time()

            def _callback(*args):
                time_delta = (time.time() - start_time) * 1000
                self.log.debug('Finished "%r" in %.2fms', func, time_delta)
                self._chain_functions(functions, callback, *args)

            func(self, *(args + (_callback,)))
        else:
            callback(*args)

    @staticmethod
    def add_preprocessor(*preprocessors_list):
        def _method_wrapper(fn):
            def _method(self, *args, **kwargs):
                self._call_preprocessors(preprocessors_list, partial(fn, self, *args, **kwargs))
            return _method
        return _method_wrapper

    def add_template_postprocessor(self, postprocessor):
        self._template_postprocessors.append(postprocessor)

    def add_early_postprocessor(self, postprocessor):
        self._early_postprocessors.append(postprocessor)

    def add_late_postprocessor(self, postprocessor):
        self._late_postprocessors.append(postprocessor)

    # Producers

    def _generic_producer(self, callback):
        self.log.debug('finishing plaintext')
        callback(self.text)

    def set_plaintext_response(self, text):
        self.text = text

    def xml_from_file(self, filename):
        return self.xml_producer.xml_from_file(filename)

    def set_xsl(self, filename):
        return self.xml_producer.set_xsl(filename)

    def set_template(self, filename):
        return self.json_producer.set_template(filename)

# coding=utf-8

import base64
from functools import partial
import httplib
import time

import tornado.curl_httpclient
import tornado.httputil
import tornado.options
import tornado.web
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPRequest
import tornado.options
import tornado.web

from frontik.async import AsyncGroup
import frontik.auth
from frontik.globals import global_stats
import frontik.handler_active_limit
from frontik.handler_debug import PageHandlerDebug
from frontik.http_client import HttpClient
import frontik.util
import frontik.producers.json_producer
import frontik.producers.xml_producer


# this function replaces __repr__ function for tornado's HTTPRequest
# HTTPRequest.body is printed only in debug mode
def context_based_repr(self):
    attrs = ("protocol", "host", "method", "uri", "version", "remote_ip")
    if tornado.options.options.debug:
        attrs += ("body",)

    args = ", ".join(["%s=%r" % (n, getattr(self, n)) for n in attrs])
    return "%s(%s, headers=%s)" % (
        self.__class__.__name__, args, dict(self.headers))


# TODO: remove after Tornado3 migration
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


class ApplicationGlobals(object):
    """ Global settings for Frontik instance """
    def __init__(self, config):
        self.config = config
        self.xml = frontik.producers.xml_producer.ApplicationXMLGlobals(config)
        self.json = frontik.producers.json_producer.ApplicationJsonGlobals(config)
        self.curl_http_client = tornado.curl_httpclient.CurlAsyncHTTPClient(max_clients=200)


class BaseHandler(tornado.web.RequestHandler):

    preprocessors = ()

    # to restore tornado.web.RequestHandler compatibility
    def __init__(self, application, request, logger, request_id=None, app_globals=None, **kwargs):
        self._prepared = False

        if request_id is None:
            raise Exception('no request_id for {} provided'.format(self.__class__))

        if app_globals is None:
            raise Exception('{} need to have app_globals'.format(self.__class__))

        self.name = self.__class__.__name__
        self.request_id = request_id
        self.log = logger
        self.log.register_handler(self)
        self.config = app_globals.config

        super(BaseHandler, self).__init__(application, request, logger=self.log, **kwargs)

        self._app_globals = app_globals
        self._debug_access = None

        self._template_postprocessors = []
        self._early_postprocessors = []
        self._late_postprocessors = []
        self._returned_methods = set()

        self._http_client = HttpClient(self, self._app_globals.curl_http_client, self.modify_http_client_request)

        # this is deprecated
        if hasattr(self.config, 'postprocessor'):
            self.add_template_postprocessor(self.config.postprocessor)

        self.text = None

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def initialize(self, logger=None, **kwargs):
        # Hides logger keyword argument from incompatible tornado versions
        super(BaseHandler, self).initialize(**kwargs)

    def prepare(self):
        self.active_limit = frontik.handler_active_limit.PageHandlerActiveLimit(self)
        self.debug = PageHandlerDebug(self)

        self.json_producer = frontik.producers.json_producer.JsonProducer(
            self, self._app_globals.json, getattr(self, 'json_encoder', None))
        self.json = self.json_producer.json

        self.xml_producer = frontik.producers.xml_producer.XmlProducer(self, self._app_globals.xml)
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

        self.finish_group = AsyncGroup(self.check_finished(self._finish_page_cb), name='finish', log=self.log.info)
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

    def set_default_headers(self):
        self._headers = tornado.httputil.HTTPHeaders({
            'Server': 'Frontik/{0}'.format(frontik.version)
        })

    def decode_argument(self, value, name=None):
        try:
            return super(BaseHandler, self).decode_argument(value, name)
        except (UnicodeError, tornado.web.HTTPError):
            self.log.warning('cannot decode utf-8 query parameter, trying other charsets')

        try:
            return frontik.util.decode_string_from_charset(value)
        except UnicodeError:
            self.log.exception('cannot decode argument, ignoring invalid chars')
            return value.decode('utf-8', 'ignore')

    # TODO: change signature after Tornado 3 migration
    def set_status(self, status_code, **kwargs):
        if status_code not in httplib.responses:
            status_code = 503
        super(BaseHandler, self).set_status(status_code, **kwargs)

    @staticmethod
    def add_callback(callback):
        IOLoop.instance().add_callback(callback)

    @staticmethod
    def add_timeout(deadline, callback):
        IOLoop.instance().add_timeout(deadline, callback)

    # Requests handling

    @tornado.web.asynchronous
    def get(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, partial(self._save_return_value, self.get_page))
        self._finish_page()

    @tornado.web.asynchronous
    def post(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, partial(self._save_return_value, self.post_page))
        self._finish_page()

    @tornado.web.asynchronous
    def head(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, partial(self._save_return_value, self.get_page))
        self._finish_page()

    @tornado.web.asynchronous
    def delete(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, partial(self._save_return_value, self.delete_page))
        self._finish_page()

    @tornado.web.asynchronous
    def put(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        self._call_preprocessors(self.preprocessors, partial(self._save_return_value, self.put_page))
        self._finish_page()

    def options(self, *args, **kwargs):
        raise HTTPError(405, headers={'Allow': ', '.join(self.__get_allowed_methods())})

    def _save_return_value(self, handler_method, *args, **kwargs):
        def is_handler_method(function_name):
            return function_name in {'get_page', 'post_page', 'put_page', 'delete_page'}

        return_value = handler_method(*args, **kwargs)

        if hasattr(self, 'handle_return_value'):
            method_name = handler_method.__name__
            if is_handler_method(method_name) and method_name not in self._returned_methods:
                self._returned_methods.add(method_name)
                self.handle_return_value(method_name, return_value)

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

    def modify_http_client_request(self, request):
        return request

    # Finish page

    def check_finished(self, callback, *args, **kwargs):
        original_callback = callback
        if args or kwargs:
            callback = partial(callback, *args, **kwargs)

        def wrapper(*args, **kwargs):
            if self._finished:
                self.log.warn('page was already finished, {0} ignored'.format(original_callback))
            else:
                callback(*args, **kwargs)

        return wrapper

    def _finish_page(self):
        self.finish_group.try_finish()

    def finish_with_postprocessors(self):
        self.finish_group.finish()

    def _finish_page_cb(self):
        if not self._finished:
            def _callback():
                self.log.stage_tag('page')

                if self.text is not None:
                    producer = self._generic_producer
                elif not self.json.is_empty():
                    producer = self.json_producer
                else:
                    producer = self.xml_producer

                self.log.info('using %s producer', producer)

                if self.apply_postprocessor:
                    producer(partial(self._call_postprocessors, self._template_postprocessors, self.finish))
                else:
                    producer(self.finish)

            self._call_postprocessors(self._early_postprocessors, _callback)
        else:
            self.log.warning('trying to finish already finished page, probably bug in a workflow, ignoring')

    def __handle_long_request(self):
        self.log.warning("long request detected (uri: {0})".format(self.request.uri))
        if tornado.options.options.kill_long_requests:
            self.send_error()

    def on_connection_close(self):
        self.finish_group.abort()
        self.log.stage_tag('page')
        self.log.log_stages(408)
        raise HTTPError(408, 'Client closed the connection: aborting request')

    def send_error(self, status_code=500, **kwargs):
        self.log.stage_tag('page')

        if self._headers_written:
            super(BaseHandler, self).send_error(status_code, **kwargs)

        self.clear()

        set_status_kwargs = {}
        if 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
            if isinstance(exception, HTTPError) and exception.reason:
                set_status_kwargs['reason'] = exception.reason

        self.set_status(status_code, **set_status_kwargs)  # TODO: add explicit reason kwarg after Tornado 3 migration

        try:
            self.write_error(status_code, **kwargs)
        except Exception:
            self.log.exception('Uncaught exception in write_error')
            if not self._finished:
                self.finish()

    def write_error(self, status_code=500, **kwargs):
        # write_error in Frontik must be asynchronous when handling custom errors (due to XSLT)
        # e.g. raise HTTPError(503) is syncronous and generates a standard Tornado error page,
        # whereas raise HTTPError(503, xml=...) will call finish_with_postprocessors()

        # the solution is to move self.finish() from send_error to write_error
        # so any write_error override must call either finish() or finish_with_postprocessors() in the end

        # in Tornado 3 it may be better to rewrite this mechanism with futures

        if 'exception' in kwargs:
            exception = kwargs['exception']  # Old Tornado
        elif 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
        else:
            exception = None

        headers = getattr(exception, 'headers', None)
        override_content = any(getattr(exception, x, None) is not None for x in ('text', 'xml', 'json'))

        finish_with_exception = exception is not None and (
            199 < status_code < 400 or  # raise HTTPError(200) to finish page immediately
            override_content
        )

        if headers:
            for (name, value) in headers.iteritems():
                self.set_header(name, value)

        if finish_with_exception:
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

            self.finish_with_postprocessors()
            return

        self.set_header('Content-Type', 'text/html; charset=UTF-8')
        return super(BaseHandler, self).write_error(status_code, **kwargs)

    def finish(self, chunk=None):
        if hasattr(self, 'finish_timeout_handle'):
            IOLoop.instance().remove_timeout(self.finish_timeout_handle)

        def _finish_with_async_hook():
            self.log.stage_tag('postprocess')

            if hasattr(self, 'active_limit'):
                self.active_limit.release()

            super(BaseHandler, self).finish(chunk)
            IOLoop.instance().add_timeout(
                time.time() + 0.1,
                partial(self.log.request_finish_hook, self._status_code, self.request.method, self.request.uri)
            )

        try:
            self._call_postprocessors(self._late_postprocessors, _finish_with_async_hook)
        except:
            self.log.exception('error during late postprocessing stage, finishing with an exception')
            self._status_code = 500
            _finish_with_async_hook()

    def flush(self, include_footers=False, **kwargs):
        self.log.stage_tag('finish')
        self.log.info('finished handler %r', self)

        if self._prepared and (self.debug.debug_mode.enabled or self.debug.debug_mode.error_debug):
            try:
                self._response_size = sum(map(len, self._write_buffer))
                original_headers = {'Content-Length': str(self._response_size)}
                response_headers = dict(
                    getattr(self, '_DEFAULT_HEADERS', {}).items() + self._headers.items(), **original_headers
                )

                original_response = {
                    'buffer': base64.encodestring(''.join(self._write_buffer)),
                    'headers': response_headers,
                    'code': self._status_code
                }

                res = self.debug.get_debug_page(
                    self._status_code, response_headers, original_response, self.log.get_current_total()
                )

                if self.debug.debug_mode.enabled:
                    # change status code only if debug was explicitly requested
                    self._status_code = 200

                if self.debug.debug_mode.inherited:
                    self.set_header(PageHandlerDebug.DEBUG_HEADER_NAME, True)

                self.set_header('Content-disposition', '')
                self.set_header('Content-Length', str(len(res)))
                self._write_buffer = [res]

            except Exception:
                self.log.exception('cannot write debug info')

        super(BaseHandler, self).flush(include_footers=False, **kwargs)

    def _log(self):
        super(BaseHandler, self)._log()
        self.log.stage_tag('flush')
        self.log.log_stages(self._status_code)

    # Preprocessors and postprocessors

    def _call_preprocessors(self, preprocessors, callback):
        self._chain_functions(iter(preprocessors), callback, 'preprocessor')

    def _call_postprocessors(self, postprocessors, callback, *args):
        self._chain_functions(iter(postprocessors), callback, 'postprocessor', *args)

    def _chain_functions(self, functions, callback, chain_type, *args):
        try:
            func = next(functions)
            start_time = time.time()

            def _callback(*args):
                time_delta = (time.time() - start_time) * 1000
                self.log.info('finished %s "%r" in %.2fms', chain_type, func, time_delta)
                self._chain_functions(functions, callback, chain_type, *args)

            func(self, *(args + (_callback,)))
        except StopIteration:
            callback(*args)

    @staticmethod
    def add_preprocessor(*preprocessors_list):
        def _method_wrapper(fn):
            def _method(self, *args, **kwargs):
                callback = partial(self._save_return_value, fn, self, *args, **kwargs)
                return self._call_preprocessors(preprocessors_list, callback)
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

    # Deprecated, use self.text directly
    def set_plaintext_response(self, text):
        self.text = text

    def xml_from_file(self, filename):
        return self.xml_producer.xml_from_file(filename)

    def set_xsl(self, filename):
        return self.xml_producer.set_xsl(filename)

    def set_template(self, filename):
        return self.json_producer.set_template(filename)


class PageHandler(BaseHandler):
    def __init__(self, application, request, logger, request_id=None, app_globals=None, **kwargs):
        super(PageHandler, self).__init__(application, request, logger, request_id, app_globals, **kwargs)

    def group(self, futures, callback=None, name=None):
        return self._http_client.group(futures, callback, name)

    def get_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None, callback=None,
                follow_redirects=True, labels=None, add_to_finish_group=True,
                parse_response=True, parse_on_error=False):

        return self._http_client.get_url(
            url, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, follow_redirects=follow_redirects, labels=labels,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def post_url(self, url, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
                 callback=None, follow_redirects=True, content_type=None, labels=None,
                 add_to_finish_group=True, parse_response=True, parse_on_error=False):

        return self._http_client.post_url(
            url, data=data, headers=headers, files=files,
            connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, follow_redirects=follow_redirects, content_type=content_type, labels=labels,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def put_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None, callback=None,
                content_type=None, labels=None, add_to_finish_group=True, parse_response=True, parse_on_error=False):

        return self._http_client.put_url(
            url, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, content_type=content_type, labels=labels,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    def delete_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None, callback=None,
                   content_type=None, labels=None, add_to_finish_group=True, parse_response=True, parse_on_error=False):

        return self._http_client.delete_url(
            url, data=data, headers=headers, connect_timeout=connect_timeout, request_timeout=request_timeout,
            callback=callback, content_type=content_type, labels=labels,
            add_to_finish_group=add_to_finish_group, parse_response=parse_response, parse_on_error=parse_on_error
        )

    # Deprecated, use PageHandler._http_client.fetch
    def fetch_request(self, request, callback, add_to_finish_group=True):
        return self._http_client.fetch(request, callback, add_to_finish_group)


class ErrorHandler(tornado.web.ErrorHandler, PageHandler):
    pass


class RedirectHandler(tornado.web.RedirectHandler, PageHandler):
    pass

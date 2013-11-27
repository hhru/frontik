# -*- coding: utf-8 -*-

from __future__ import with_statement

from functools import partial
from itertools import imap
import simplejson as json
import re
import time

import lxml.etree as etree
import tornado.curl_httpclient
import tornado.httpclient
import tornado.options
import tornado.web
import tornado.ioloop
from tornado.httpserver import HTTPRequest

import frontik.async
import frontik.auth
import frontik.frontik_logging as frontik_logging
import frontik.future as future
import frontik.handler_whc_limit
import frontik.handler_debug
import frontik.jobs
import frontik.util
import frontik.xml_util
import frontik.xsl_producer


# this function replaces __repr__ function for tornado's HTTPRequest
# the difference is in handling body attribute: values of various `password` fields in POST requests
# are replaced with '***' to secure them from showing up in the logs
def context_based_repr(self):
    attrs = ["protocol", "host", "method", "uri", "version", "remote_ip"]
    secured_body = self.body
    # ignore multipart/form-data to not slow down file uploads
    if self.method == "POST" and not self.headers.get("Content-Type", "").startswith("multipart/form-data"):
        secure_url_params = ('password', 'passwd', 'b', 'newPassword', 'newPasswordConfirm', 'passwordConfirm',
                             'passwordAdd')
        secure_regexp = r'(^|&)({0})(=[^&]+)(?=(&|$))'.format('|'.join(secure_url_params))
        secured_body = re.sub(secure_regexp,
                              lambda m: ''.join([m.groups()[0], m.groups()[1], '=***']),
                              secured_body)
    args = ", ".join(["%s=%r" % (n, getattr(self, n)) for n in attrs])
    args = ", ".join([args, "body=%r" % secured_body])
    return "%s(%s, headers=%s)" % (
        self.__class__.__name__, args, dict(self.headers))


HTTPRequest.__repr__ = context_based_repr


def _parse_response(response, logger=frontik_logging.log, parser=None, response_type=None):
    try:
        data = parser(response.body)
    except:
        _preview_len = 100

        if len(response.body) > _preview_len:
            body_preview = '{0}...'.format(response.body[:_preview_len])
        else:
            body_preview = response.body

        logger.exception('failed to parse {0} response from {1}, bad data: "{2}"'.format(
            response_type, response.effective_url, body_preview))
        return False, etree.Element('error', url=response.effective_url, reason='invalid {0}'.format(response_type))

    return True, data

_xml_parser = etree.XMLParser(strip_cdata=False)
_parse_response_xml = partial(_parse_response,
                              parser=lambda x: etree.fromstring(x, parser=_xml_parser),
                              response_type='XML')

_parse_response_json = partial(_parse_response,
                               parser=json.loads,
                               response_type='JSON')

default_request_types = {
    re.compile(".*xml.?"): _parse_response_xml,
    re.compile(".*json.?"): _parse_response_json
}

AsyncGroup = frontik.async.AsyncGroup


class HTTPError(tornado.web.HTTPError):
    """ An exception that will turn into an HTTP error response """
    def __init__(self, status_code, log_message=None, headers=None, *args, **kwargs):
        tornado.web.HTTPError.__init__(self, status_code, log_message, *args)
        self.headers = headers if headers is not None else {}
        for data in ('text', 'xml', 'xsl'):
            setattr(self, data, kwargs.setdefault(data, None))


class Stats(object):
    def __init__(self):
        self.page_count = 0
        self.http_reqs_count = 0
        self.http_reqs_size_sum = 0
        self.start_time = time.time()

    def next_request_id(self):
        self.page_count += 1
        return self.page_count

stats = Stats()


class PageHandlerGlobals(object):
    """ Global settings for Frontik instance """
    def __init__(self, app_package):
        self.config = app_package.config

        self.xml = frontik.xml_util.PageHandlerXMLGlobals(app_package.config)

        self.http_client = tornado.curl_httpclient.CurlAsyncHTTPClient(max_clients=200)


class PageHandler(tornado.web.RequestHandler):

    # to restore tornado.web.RequestHandler compatibility
    def __init__(self, application, request, ph_globals=None, **kwargs):
        self.handler_started = time.time()
        self._prepared = False

        if ph_globals is None:
            raise Exception("%s need to have ph_globals" % PageHandler)

        self.name = self.__class__.__name__
        self.request_id = request.headers.get('X-Request-Id', str(stats.next_request_id()))
        logger_name = '.'.join(filter(None, [self.request_id, getattr(ph_globals.config, 'app_name', None)]))
        self.log = frontik_logging.PageLogger(self, logger_name, request.path or request.uri)

        tornado.web.RequestHandler.__init__(self, application, request, logger=self.log, **kwargs)

        self.ph_globals = ph_globals
        self.config = self.ph_globals.config
        self.http_client = self.ph_globals.http_client
        self.debug_access = None

        self._template_postprocessors = []
        self._early_postprocessors = []
        self._late_postprocessors = []

        if hasattr(self.config, 'postprocessor'):
            self.add_template_postprocessor(self.config.postprocessor)

        self.text = None

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def prepare(self):
        self.whc_limit = frontik.handler_whc_limit.PageHandlerWHCLimit(self)
        self.debug = frontik.handler_debug.PageHandlerDebug(self)
        self.log.info('page module: %s', self.__module__)

        self.xml = frontik.xsl_producer.XslProducer(self)
        self.doc = self.xml.doc  # backwards compatibility for self.doc.put

        if self.get_argument('nopost', None) is not None:
            self.require_debug_access()
            self.apply_postprocessor = False
            self.log.debug('apply_postprocessor==False due to ?nopost query arg')
        else:
            self.apply_postprocessor = True

        if tornado.options.options.long_request_timeout:
            # add long requests timeout
            self.finish_timeout_handle = tornado.ioloop.IOLoop.instance().add_timeout(
                time.time() + tornado.options.options.long_request_timeout, self.__handle_long_request)

        self.finish_group = frontik.async.AsyncGroup(self.async_callback(self._finish_page_cb),
                                                     name='finish', log=self.log.debug)
        self._prepared = True

    def require_debug_access(self, login=None, passwd=None):
        if self.debug_access is None:
            if tornado.options.options.debug:
                self.debug_access = True
            else:
                check_login = login if login is not None else tornado.options.options.debug_login
                check_passwd = passwd if passwd is not None else tornado.options.options.debug_password

                self.debug_access = frontik.auth.passed_basic_auth(
                    self, check_login, check_passwd)

            if not self.debug_access:
                raise HTTPError(401, headers={'WWW-Authenticate': 'Basic realm="Secure Area"'})

    def decode_argument(self, value, name=None):
        try:
            return super(PageHandler, self).decode_argument(value, name)
        except UnicodeDecodeError:
            self.log.exception('Cannot decode unicode query parameter, trying other charsets')

        try:
            return frontik.util.decode_string_from_charset(value)
        except Exception:
            self.log.exception('Cannot decode query parameter, falling back to empty string')
            return ''

    def async_callback(self, callback, *args, **kw):
        return tornado.web.RequestHandler.async_callback(self, self.check_finished(callback, *args, **kw))

    def check_finished(self, callback, *args, **kwargs):
        if args or kwargs:
            callback = partial(callback, *args, **kwargs)

        def wrapper(*args, **kwargs):
            if self._finished:
                self.log.warn('Page was already finished, %s ignored', callback)
            else:
                callback(*args, **kwargs)

        return wrapper

    # Requests handling

    @tornado.web.asynchronous
    def post(self, *args, **kw):
        self.log.stage_tag('prepare')
        if not self._finished:
            self.post_page()
            self.finish_page()

    @tornado.web.asynchronous
    def get(self, *args, **kw):
        self.log.stage_tag('prepare')
        if not self._finished:
            self.get_page()
            self.finish_page()

    @tornado.web.asynchronous
    def head(self, *args, **kwargs):
        self.log.stage_tag('prepare')
        if not self._finished:
            self.get_page()
            self.finish_page()

    def delete(self, *args, **kwargs):
        raise HTTPError(405, headers={"Allow": "GET, POST"})

    def put(self, *args, **kwargs):
        raise HTTPError(405, headers={"Allow": "GET, POST"})

    def options(self, *args, **kwargs):
        raise HTTPError(405, headers={"Allow": "GET, POST"})

    def get_page(self):
        """ This method should be implemented in the subclass """
        raise HTTPError(405, header={'Allow': 'POST'})

    def post_page(self):
        """ This method should be implemented in the subclass """
        raise HTTPError(405, headers={'Allow': 'GET'})

    # HTTP client methods

    DEFAULT_CONNECT_TIMEOUT = 0.5
    DEFAULT_REQUEST_TIMEOUT = 2

    def get_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None, callback=None,
                follow_redirects=True, parse_response=True, labels=None):

        placeholder = future.Placeholder()
        request = frontik.util.make_get_request(
            url, {} if data is None else data, {} if headers is None else headers,
            connect_timeout, request_timeout, follow_redirects)

        request._frontik_labels = labels
        self.fetch_request(request, partial(self._parse_response, placeholder, callback, parse_response=parse_response))
        return placeholder

    def post_url(self, url, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
                 follow_redirects=True, content_type=None, callback=None, parse_response=True, labels=None):

        placeholder = future.Placeholder()
        request = frontik.util.make_post_request(
            url, data, {} if headers is None else headers, {} if files is None else files,
            connect_timeout, request_timeout, follow_redirects, content_type)

        request._frontik_labels = labels
        self.fetch_request(request, partial(self._parse_response, placeholder, callback, parse_response=parse_response))
        return placeholder

    def put_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None, callback=None,
                parse_response=True, labels=None):

        placeholder = future.Placeholder()
        request = frontik.util.make_put_request(
            url, data, {} if headers is None else headers,
            connect_timeout, request_timeout)

        request._frontik_labels = labels
        self.fetch_request(request, partial(self._parse_response, placeholder, callback, parse_response=parse_response))
        return placeholder

    def delete_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None, callback=None,
                   parse_response=True, labels=None):

        placeholder = future.Placeholder()
        request = frontik.util.make_delete_request(
            url, data, {} if headers is None else headers,
            connect_timeout, request_timeout)

        request._frontik_labels = labels
        self.fetch_request(request, partial(self._parse_response, placeholder, callback, parse_response=parse_response))
        return placeholder

    def fetch_request(self, request, callback):
        """ Tornado HTTP client compatible method """
        if not self._finished:
            stats.http_reqs_count += 1

            if self._prepared and self.debug.debug_mode.pass_debug:
                authorization = self.request.headers.get('Authorization')
                request.headers[frontik.handler_debug.PageHandlerDebug.DEBUG_HEADER_NAME] = True
                if authorization is not None:
                    request.headers['Authorization'] = authorization

            request.headers['X-Request-Id'] = self.request_id

            if request.connect_timeout is None:
                request.connect_timeout = self.DEFAULT_CONNECT_TIMEOUT
            if request.request_timeout is None:
                request.request_timeout = self.DEFAULT_REQUEST_TIMEOUT

            request.connect_timeout *= tornado.options.options.timeout_multiplier
            request.request_timeout *= tornado.options.options.timeout_multiplier

            return self.http_client.fetch(request, self.finish_group.add(
                self.async_callback(self._log_response, request, callback)))
        else:
            self.log.warn('attempted to make http request to %s while page is already finished; ignoring', request.url)

    def _log_response(self, request, callback, response):
        try:
            if response.body is not None:
                stats.http_reqs_size_sum += len(response.body)
        except TypeError:
            self.log.warn('got strange response.body of type %s', type(response.body))

        try:
            debug_extra = {}
            if response.headers.get(frontik.handler_debug.PageHandlerDebug.DEBUG_HEADER_NAME):
                debug_response = etree.XML(response.body)
                original_response = debug_response.xpath('//original-response')
                if original_response:
                    response_info = frontik.xml_util.xml_to_dict(original_response[0])
                    debug_response.remove(original_response[0])
                    debug_extra['_debug_response'] = debug_response
                    response = frontik.util.create_fake_response(request, response, **response_info)

            debug_extra.update({'_response': response, '_request': request})
            if getattr(request, '_frontik_labels', None) is not None:
                debug_extra['_labels'] = request._frontik_labels

            self.log.debug(
                'got {code}{size} {url} in {time:.2f}ms'.format(
                    code=response.code,
                    url=response.effective_url,
                    size=' {0:e} bytes'.format(len(response.body)) if response.body is not None else '',
                    time=response.request_time * 1000
                ),
                extra=debug_extra
            )
        except Exception:
            self.log.exception('Cannot log response info')

        if callable(callback):
            callback(response)

    def _parse_response(self, placeholder, callback, response, parse_response=True):
        result = None
        if response.error:
            placeholder.set_data(self.show_response_error(response))
        elif not parse_response:
            result = response.body
        elif response.code != 204:
            content_type = response.headers.get('Content-Type', '')
            for k, v in default_request_types.iteritems():
                if k.search(content_type):
                    good_result, data = v(response)
                    result = data if good_result else None
                    placeholder.set_data(data)
                    break

        if callable(callback):
            callback(result, response)

    def show_response_error(self, response):
        self.log.warn('%s failed %s (%s)', response.code, response.effective_url, str(response.error))
        try:
            data = etree.Element(
                'error', url=response.effective_url, reason=str(response.error), code=str(response.code))
        except ValueError:
            self.log.warn("Cannot add information about response head in debug, can't be serialized in xml.")

        if response.body:
            try:
                data.append(etree.Comment(response.body.replace("--", "%2D%2D")))
            except ValueError:
                self.log.warn('Cannot add debug info in XML comment with unparseable response.body: non-ASCII response')

        return data

    # Finish page

    def finish_page(self):
        self.finish_group.try_finish()

    def _force_finish(self):
        self.finish_group.finish()

    def _finish_page_cb(self):
        if not self._finished:
            self.log.stage_tag('page')

            def __callback():
                producer = self.xml if self.text is None else self.__generic_producer
                if self.apply_postprocessor:
                    producer(partial(self.__call_postprocessors, self._template_postprocessors[:], self.finish))
                else:
                    producer(self.finish)

            self.__call_postprocessors(self._early_postprocessors[:], __callback)
        else:
            self.log.warn('trying to finish already finished page, probably bug in a workflow, ignoring')

    def __handle_long_request(self):
        self.log.warning("long request detected (uri: {0})".format(self.request.uri))
        if tornado.options.options.kill_long_requests:
            self.send_error()

    def __call_postprocessors(self, postprocessors, callback, *args):
        def __chain_postprocessor(postprocessors, start_time, *args):
            if start_time is not None:
                time_delta = (time.time() - start_time) * 1000
                self.log.debug('Finished postprocessor "{0!r}" in {1:.2f}ms'.format(postprocessors.pop(0), time_delta))

            if postprocessors:
                postprocessor = postprocessors[0]
                self.log.debug('Started postprocessor "{0!r}"'.format(postprocessor))
                postprocessor_callback = partial(__chain_postprocessor, postprocessors, time.time())
                postprocessor(self, *(args + (postprocessor_callback,)))
            else:
                callback(*args)

        __chain_postprocessor(postprocessors[:], None, *args)

    def send_error(self, status_code=500, headers=None, **kwargs):
        headers = {} if headers is None else headers
        exception = kwargs.get('exception', None)
        finish_with_exception = exception is not None and (
            199 < status_code < 400 or  # raise HTTPError(200) to finish page immediately
            getattr(exception, 'xml', None) is not None or getattr(exception, 'text', None) is not None)

        if finish_with_exception:
            self.set_status(status_code)
            for (name, value) in headers.iteritems():
                self.set_header(name, value)

            if getattr(exception, 'text', None) is not None:
                self.text = exception.text
            elif getattr(exception, 'xml', None) is not None:
                self.doc.put(exception.xml)
                if getattr(exception, 'xsl', None) is not None:
                    self.set_xsl(exception.xsl)

            self._force_finish()
            return

        elif self._prepared and self.debug.debug_mode.write_debug:
            # debug can be shown on any error if it is enabled in config
            self.debug.debug_mode.error_debug = True

        return super(PageHandler, self).send_error(status_code, headers=headers, **kwargs)

    def finish(self, chunk=None):
        if hasattr(self, 'finish_timeout_handle'):
            tornado.ioloop.IOLoop.instance().remove_timeout(self.finish_timeout_handle)

        if not self._finished:
            if hasattr(self, 'whc_limit'):
                self.whc_limit.release()

        try:
            self.__call_postprocessors(self._late_postprocessors[:], partial(super(PageHandler, self).finish, chunk))
        except Exception:
            self.log.exception('Error during late postprocessing stage, finishing with an exception')
            self._status_code = 500
            super(PageHandler, self).finish(chunk)

    def flush(self, include_footers=False, **kwargs):
        self.log.stage_tag('postprocess')
        self.log.process_stages(self._status_code)

        if self._prepared and (self.debug.debug_mode.enabled or self.debug.debug_mode.error_debug):
            try:
                self._response_size = sum(imap(len, self._write_buffer))
                original_headers = {'Content-Length': str(self._response_size)}
                response_headers = dict(self._headers, **original_headers)
                original_response = {
                    'buffer': ''.join(self._write_buffer),
                    'headers': response_headers,
                    'code': self._status_code
                }

                res = self.debug.get_debug_page(self._status_code, response_headers, original_response)

                if self.debug.debug_mode.enabled:
                    # change status code only if debug was explicitly requested
                    self._status_code = 200

                if self.debug.debug_mode.inherited:
                    self.set_header(frontik.handler_debug.PageHandlerDebug.DEBUG_HEADER_NAME, True)

                self.set_header('Content-disposition', '')
                self.set_header('Content-Length', str(len(res)))
                self._write_buffer = [res]

            except Exception:
                self.log.exception('Cannot write debug info')

        tornado.web.RequestHandler.flush(self, include_footers=False, **kwargs)
        self.log.request_finish_hook()

    # Postprocessors and producers

    def add_template_postprocessor(self, postprocessor):
        self._template_postprocessors.append(postprocessor)

    def add_early_postprocessor(self, postprocessor):
        self._early_postprocessors.append(postprocessor)

    def add_late_postprocessor(self, postprocessor):
        self._late_postprocessors.append(postprocessor)

    def __generic_producer(self, callback):
        self.log.debug('finishing plaintext')
        callback(self.text)

    def set_plaintext_response(self, text):
        self.text = text

    def xml_from_file(self, filename):
        return self.ph_globals.xml.xml_cache.load(filename, log=self.log)

    def set_xsl(self, filename):
        return self.xml.set_xsl(filename)

# -*- coding: utf-8 -*-

from __future__ import with_statement

from functools import partial
from itertools import imap
import simplejson as json
import re
import time
import frontik_logging

import lxml.etree as etree
import tornado.curl_httpclient
import tornado.httpclient
import tornado.options
import tornado.web
import tornado.ioloop

import frontik.async
import frontik.auth
import frontik.util
import frontik.xml_util
import frontik.jobs
import frontik.handler_xml
import frontik.handler_whc_limit
import frontik.handler_debug
import frontik.future as future

from tornado.httpserver import HTTPRequest


# this function replaces __repr__ function for tornado's HTTPRequest
# the difference is in handling body attribute: values of various `password` fields in POST requests
# are replaced with '***' to secure them from showing up in the logs
def context_based_repr(self):
    attrs = ["protocol", "host", "method", "uri", "version", "remote_ip"]
    secured_body = self.body
    if self.method == "POST":
        if self.headers.get("Content-Type", "").startswith("multipart/form-data"):
            lines = self.body.split("\n")
            header = 'Content-Disposition: form-data; name="password"'
            for i in xrange(len(lines)):
                if i > 1 and lines[i - 2].find(header) > -1:
                    lines[i] = "***"
            secured_body = "\n".join(lines)
        else:
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


def _parse_response_smth(response, logger=frontik_logging.log, parser=None, type_=None):
    _preview_len = 100
    try:
        data = parser(response.body)
    except:
        if len(response.body) > _preview_len:
                body_preview = '{0}...'.format(response.body[:_preview_len])
        else:
            body_preview = response.body

        logger.exception('failed to parse {2} response from {0} Bad data:"{1}"'.format(
            response.effective_url, body_preview, type_))
        return False, etree.Element('error', dict(url=response.effective_url, reason='invalid {0}'.format(type_)))

    return True, data

_xml_parser = etree.XMLParser(strip_cdata=False)
_parse_response_xml = partial(_parse_response_smth,
                              parser=lambda x: etree.fromstring(x, parser=_xml_parser),
                              type_='XML')

_parse_response_json = partial(_parse_response_smth,
                               parser=json.loads,
                               type_='JSON')

default_request_types = {
    re.compile(".*xml.?"): _parse_response_xml,
    re.compile(".*json.?"): _parse_response_json
}

# TODO cleanup this after release of frontik with frontik.async
AsyncGroup = frontik.async.AsyncGroup


class HTTPError(tornado.web.HTTPError):
    """An exception that will turn into an HTTP error response."""
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
    """
    Объект с настройками для всех хендлеров
    """
    def __init__(self, app_package):
        self.config = app_package.config

        self.xml = frontik.handler_xml.PageHandlerXMLGlobals(app_package.config)

        self.http_client = tornado.curl_httpclient.CurlAsyncHTTPClient(
            max_clients=200, max_simultaneous_connections=200)

        self.executor = frontik.jobs.executor()


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

        self.text = None

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def prepare(self):
        self.whc_limit = frontik.handler_whc_limit.PageHandlerWHCLimit(self)
        self.debug = frontik.handler_debug.PageHandlerDebug(self)
        self.log.info('page module: %s', self.__module__)

        self.xml = frontik.handler_xml.PageHandlerXML(self)
        self.doc = self.xml.doc  # backwards compatibility for self.doc.put

        if self.get_argument('nopost', None) is not None:
            self.require_debug_access()
            self.apply_postprocessor = False
            self.log.debug('apply_postprocessor==False due to ?nopost query arg')
        else:
            self.apply_postprocessor = True

        self.finish_group = frontik.async.AsyncGroup(self.async_callback(self._finish_page_cb),
                                                     name='finish',
                                                     log=self.log.debug)
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

    def get_error_html(self, status_code, **kwargs):
        if self._prepared and self.debug.debug_mode.write_debug:
            debug_is_finished = not self.debug.debug_mode.inherited
            return self.debug.get_debug_page(status_code, self._headers, finish_debug=debug_is_finished)
        else:
            #if not prepared (for example, working handlers count limit) or not in
            #debug mode use default tornado error page
            return super(PageHandler, self).get_error_html(status_code, **kwargs)

    def send_error(self, status_code=500, headers=None, **kwargs):
        if headers is None:
            headers = {}
        exception = kwargs.get("exception", None)
        need_finish = exception is not None and (199 < status_code < 400 or
            not(getattr(exception, "xml", None) is None and getattr(exception, "text", None) is None))

        if need_finish:
            self.set_status(status_code)
            for (name, value) in headers.iteritems():
                self.set_header(name, value)

            if getattr(exception, "text", None) is not None:
                self.text = exception.text
            if getattr(exception, "xml", None) is not None:
                self.doc.put(exception.xml)
                if getattr(exception, "xsl", None) is not None:
                    self.set_xsl(exception.xsl)
            self._force_finish()

        else:
            return super(PageHandler, self).send_error(status_code, headers=headers, **kwargs)

    @tornado.web.asynchronous
    def post(self, *args, **kw):
            self.post_page()
            self.finish_page()

    @tornado.web.asynchronous
    def get(self, *args, **kw):
        if not self._finished:
            self.get_page()
            self.finish_page()

    @tornado.web.asynchronous
    def head(self, *args, **kwargs):
        if not self._finished:
            self.get_page()
            self.finish_page()

    def delete(self, *args, **kwargs):
        raise HTTPError(405, headers={"Allow": "GET, POST"})

    def put(self, *args, **kwargs):
        raise HTTPError(405, headers={"Allow": "GET, POST"})

    def options(self, *args, **kwargs):
        raise HTTPError(405, headers={"Allow": "GET, POST"})

    def finish(self, chunk = None):
        if hasattr(self, 'whc_limit'):
            self.whc_limit.release()

        self.log.process_stages(self._status_code)

        tornado.web.RequestHandler.finish(self, chunk)

    def flush(self, include_footers=False, **kwargs):
        orig_write_buffer = self._write_buffer
        try:
            # if debug_mode is on: ignore any output we intended to write
            # and use debug log instead
            if hasattr(self, 'debug') and self.debug.debug_mode.enabled:
                self._response_size = sum(imap(len, self._write_buffer))

                if self.debug.debug_mode.return_response:
                    original_headers = {'Content-Length': str(self._response_size)}
                    response_headers = dict(self._headers, **original_headers)
                    original_response = {
                        'buffer': ''.join(self._write_buffer),
                        'headers': response_headers,
                        'code': self._status_code
                    }

                    self.set_header(frontik.handler_debug.PageHandlerDebug.INHERIT_DEBUG_HEADER_NAME, True)
                else:
                    response_headers = self._headers
                    original_response = None

                res = self.debug.get_debug_page(self._status_code, response_headers, original_response)

                if not self.debug.debug_mode.return_response:
                    self.set_header('Content-Type', 'text/html')

                self.set_header('Content-disposition', '')
                self.set_header('Content-Length', str(len(res)))
                self._write_buffer = [res]
                self._status_code = 200

            if hasattr(self, 'debug') and self.debug.debug_mode.profile:
                profiler_document = self.debug.get_profiler_template()
                if profiler_document is not None:
                    match = tornado.options.options.debug_profiler_tag
                    buff = ''.join(self._write_buffer)
                    res = buff.replace(match, profiler_document)
                    self.set_header('Content-Length', str(len(res)))
                    self._write_buffer = [res]
                    if match in buff:
                        self.log.debug('Profiler component added before %s tag' % match)

        except Exception:
            self.log.debug('Couldnt write debug info')
            self._write_buffer = orig_write_buffer

        tornado.web.RequestHandler.flush(self, include_footers=False, **kwargs)
        self.log.request_finish_hook()

    def get_page(self):
        """ Эта функция должна быть переопределена в наследнике и
        выполнять актуальную работу хендлера """
        raise HTTPError(405, header={"Allow": "POST"})

    def post_page(self):
        """ Эта функция должна быть переопределена в наследнике и
        выполнять актуальную работу хендлера """
        raise HTTPError(405, headers={"Allow": "GET"})

    ###

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

    ###

    def fetch_request(self, req, callback):
        if not self._finished:
            stats.http_reqs_count += 1
            def _callback(response):
                try:
                    stats.http_reqs_size_sum += len(response.body)
                except TypeError:
                    if response.body is not None:
                        self.log.warn('got strange response.body of type %s', type(response.body))
                callback(response)

            if hasattr(self, 'debug') and self.debug.debug_mode.pass_further:
                req.headers[frontik.handler_debug.PageHandlerDebug.INHERIT_DEBUG_HEADER_NAME] = True
                req.headers['Authorization'] = self.request.headers.get('Authorization', None)

            req.headers['X-Request-Id'] = self.request_id
            req.connect_timeout *= tornado.options.options.timeout_multiplier
            req.request_timeout *= tornado.options.options.timeout_multiplier

            return self.http_client.fetch(req, self.finish_group.add(self.async_callback(_callback)))
        else:
            self.log.warn('attempted to make http request to %s while page is already finished; ignoring', req.url)

    def get_url(self, url, data=None, headers=None, connect_timeout=0.5, request_timeout=2, callback=None,
                follow_redirects=True, request_types=None):

        placeholder = future.Placeholder()
        request = frontik.util.make_get_request(url,
                                                {} if data is None else data,
                                                {} if headers is None else headers,
                                                connect_timeout,
                                                request_timeout,
                                                follow_redirects)

        self.fetch_request(request, partial(self._fetch_request_response, placeholder, callback, request,
                                            request_types=request_types))
        return placeholder

    def post_url(self, url, data='', headers=None, files=None, connect_timeout=0.5, request_timeout=2,
                 follow_redirects=True, content_type=None, callback=None, request_types=None):

        placeholder = future.Placeholder()
        request = frontik.util.make_post_request(url,
                                                 data,
                                                 {} if headers is None else headers,
                                                 {} if files is None else files,
                                                 connect_timeout,
                                                 request_timeout,
                                                 follow_redirects,
                                                 content_type)

        self.fetch_request(request, partial(self._fetch_request_response, placeholder, callback, request,
                                            request_types=request_types))
        return placeholder

    def put_url(self, url, data='', headers=None, connect_timeout=0.5, request_timeout=2, callback=None,
                request_types=None):

        placeholder = future.Placeholder()
        request = frontik.util.make_put_request(url,
                                                data,
                                                {} if headers is None else headers,
                                                connect_timeout,
                                                request_timeout)

        self.fetch_request(request, partial(self._fetch_request_response, placeholder, callback, request,
                                            request_types=request_types))
        return placeholder

    def delete_url(self, url, data='', headers=None, connect_timeout=0.5, request_timeout=2, callback=None,
                   request_types=None):

        placeholder = future.Placeholder()
        request = frontik.util.make_delete_request(url,
                                                   data,
                                                   {} if headers is None else headers,
                                                   connect_timeout,
                                                   request_timeout)

        self.fetch_request(request, partial(self._fetch_request_response, placeholder, callback, request,
                                            request_types=request_types))
        return placeholder

    def _fetch_request_response(self, placeholder, callback, request, response, request_types=None):
        debug_extra = {}
        if response.headers.get(frontik.handler_debug.PageHandlerDebug.INHERIT_DEBUG_HEADER_NAME):
            debug_response = etree.XML(response.body)
            original_response = debug_response.xpath('//original-response')
            if original_response is not None:
                response_info = frontik.xml_util.xml_to_dict(original_response[0])
                debug_response.remove(original_response[0])
                debug_extra['_debug_response'] = debug_response
                response = frontik.util.create_fake_response(request, response, **response_info)

        debug_extra.update({'_response': response, '_request': request})
        self.log.debug(
            'got {code}{size} {url} in {time:.2f}ms'.format(
                code=response.code,
                url=response.effective_url,
                size=' {0:e} bytes'.format(len(response.body)) if response.body is not None else '',
                time=response.request_time * 1000
            ),
            extra=debug_extra
        )

        if not request_types:
            request_types = default_request_types
        result = None
        if response.error:
            placeholder.set_data(self.show_response_error(response))
        elif response.code != 204:
            content_type = response.headers.get('Content-Type', '')
            for k, v in request_types.iteritems():
                if k.search(content_type):
                    good_result, data = v(response)
                    if good_result:
                        result = data
                    else:
                        result = None
                    placeholder.set_data(data)
                    break
        if callback:
            callback(result, response)

    def show_response_error(self, response):
        self.log.warn('%s failed %s (%s)', response.code, response.effective_url, str(response.error))
        try:
            data = etree.Element('error',
                                 dict(url=response.effective_url, reason=str(response.error), code=str(response.code)))
        except ValueError:
            self.log.warn("Could not add information about response head in debug, can't be serialized in xml.")

        if response.body:
            try:
                data.append(etree.Comment(response.body.replace("--", "%2D%2D")))
            except ValueError:
                self.log.warn("Could not add debug info in XML comment with unparseable response.body. non-ASCII response.")

        return data

    ###

    def set_plaintext_response(self, text):
        self.text = text

    ###

    def finish_page(self):
        self.finish_group.try_finish()

    def _force_finish(self):
        self.finish_group.finish()

    def _finish_page_cb(self):
        if not self._finished:
            self.log.stage_tag("page")

            if self.text is not None:
                self._finish_with_postprocessor(self._prepare_finish_plaintext())
            else:
                self.xml.finish_xml(self.async_callback(self._finish_with_postprocessor))
        else:
            self.log.warn('trying to finish already finished page, probably bug in a workflow, ignoring')

    def _finish_with_postprocessor(self, res):
        if hasattr(self.config, 'postprocessor'):
            if self.apply_postprocessor:
                self.log.debug('applying postprocessor')
                self.async_callback(self.config.postprocessor)(self, res, self.async_callback(partial(self._wait_postprocessor, time.time())))
            else:
                self.log.debug('skipping postprocessor')
                self.finish(res)
        else:
            self.finish(res)

    def _wait_postprocessor(self, start_time, data):
        self.log.stage_tag("postprocess")
        self.log.debug("applied postprocessor '%s' in %.2fms",
                       self.config.postprocessor, (time.time() - start_time) * 1000)
        self.finish(data)

    def _prepare_finish_plaintext(self):
        self.log.debug("finishing plaintext")
        return self.text

    ###

    def xml_from_file(self, filename):
        return self.xml.xml_from_file(filename)

    def set_xsl(self, filename):
        return self.xml.set_xsl(filename)

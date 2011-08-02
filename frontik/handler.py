# -*- coding: utf-8 -*-

from __future__ import with_statement

from functools import partial
import json
import re
import time
import traceback

import lxml.etree as etree
import tornado.curl_httpclient
import tornado.httpclient
import tornado.options
import tornado.web
import tornado.ioloop

import frontik.async
import frontik.auth
import frontik.util
import frontik.handler_xml
import frontik.handler_whc_limit
import frontik.handler_xml_debug
import frontik.future as future

import logging
log = logging.getLogger('frontik.handler')


def _parse_response_xml(response, logger = log):
    '''
    return :: (placeholder_data, response_as_xml)
    None - в случае ошибки парсинга
    '''

    try:
        element = etree.fromstring(response.body)
    except:
        if len(response.body) > 100:
            body_preview = '{0}...'.format(response.body[:100])
        else:
            body_preview = response.body

        logger.warn('failed to parse XML response from %s data "%s"',
                         response.effective_url,
                         body_preview)

        return (False, etree.Element('error', dict(url = response.effective_url, reason = 'invalid XML')))
    
    return (True, element)


def _parse_response_json(response, logger = log):
    try:
        data = json.loads(response.body)
    except:
        if len(response.body) > 100:
            body_preview = '{0}...'.format(response.body[:100])
        else:
            body_preview = response.body

        logger.warn('failed to parse JSON response from %s data "%s"',
                         response.effective_url,
                         body_preview)

        return (False, etree.Element('error', dict(url = response.effective_url, reason = 'invalid JSON')))

    return (True, data)

default_request_types = {
          re.compile(".*xml.?"): _parse_response_xml,
          re.compile(".*json.?"): _parse_response_json
          }

# TODO cleanup this after release of frontik with frontik.async
AsyncGroup = frontik.async.AsyncGroup

class HTTPError(tornado.web.HTTPError):
    """An exception that will turn into an HTTP error response."""
    def __init__(self, status_code, headers = None, log_message=None, *args, **kwargs):
        if headers is None:
            headers = {}
        for data in ["text", "xml", "xsl"]:
            setattr(self, data, kwargs.setdefault(data, None))
        self.status_code = status_code
        self.log_message = log_message
        self.headers = headers
        self.args = args

class Stats(object):
    def __init__(self):
        self.page_count = 0
        self.http_reqs_count = 0

    def next_request_id(self):
        self.page_count += 1
        return self.page_count

stats = Stats()

class PageLogger(logging.Logger):
    '''
    This class is supposed to fix huge memory 'leak' in logging
    module. I.e. every call to logging.getLogger(some_unique_name)
    wastes memory as resulting logger is memoized by
    module. PageHandler used to create unique logger on each request
    by call logging.getLogger('frontik.handler.%s' %
    (self.request_id,)). This lead to wasting about 10Mb per 10K
    requests.
    '''

    def __init__(self, name, page, zero_time):
        logging.Logger.__init__(self, 'frontik.handler.{0}'.format(name))
        self.page = page
        self._time = zero_time
        self.stages = []


    def handle(self, record):
        logging.Logger.handle(self, record)
        log.handle(record)

    def stage_tag(self, stage):
        self._stage_tag(stage, (time.time() - self._time) * 1000)
        self._time = time.time()

    def _stage_tag(self, stage, time_delta):
        self.stages.append((stage, time_delta))
        self.debug('Stage: {stage}'.format(stage = stage))

    def stage_tag_backdate(self, stage, time_delta):
        self._stage_tag(stage, time_delta)

    def process_stages(self):
        self.debug("Stages for {0} : ".format(self.page) + " ".join(["{0}:{1:.2f}ms".format(k, v) for k, v in self.stages]))


class PageHandlerGlobals(object):
    '''
    Объект с настройками для всех хендлеров
    '''
    def __init__(self, app_package):
        self.config = app_package.config

        self.xml = frontik.handler_xml.PageHandlerXMLGlobals(app_package.config)

        self.http_client = tornado.curl_httpclient.CurlAsyncHTTPClient(max_clients = 200, max_simultaneous_connections = 200)



class PageHandler(tornado.web.RequestHandler):

    # to restore tornado.web.RequestHandler compatibility
    def __init__(self, application, request, ph_globals=None, **kwargs):
        self.handler_started = time.time()
        self._prepared = False

        self.name = self.__class__.__name__
        self.request_id = request.headers.get('X-Request-Id', stats.next_request_id())
        if hasattr(ph_globals.config, 'app_name') and ph_globals.config.app_name:
            handler_name = '{0}.{1}'.format(ph_globals.config.app_name, self.request_id)
        else:
            handler_name = self.request_id
        self.log = PageLogger(handler_name, request.path or request.uri, self.handler_started,)

        tornado.web.RequestHandler.__init__(self, application, request, logger = self.log, **kwargs)

        if ph_globals is None:
            raise Exception("%s need to have ph_globals" % PageHandler)

        self.ph_globals = ph_globals
        self.config = self.ph_globals.config
        self.http_client = self.ph_globals.http_client

        self.debug_access = None

        self.text = None

    def prepare(self):
        self.whc_limit = frontik.handler_whc_limit.PageHandlerWHCLimit(self)

        self.debug = frontik.handler_xml_debug.PageHandlerDebug(self)

        self.xml = frontik.handler_xml.PageHandlerXML(self)
        self.doc = self.xml.doc # backwards compatibility for self.doc.put

        if self.get_argument('nopost', None) is not None:
            self.require_debug_access()
            self.apply_postprocessor = False
            self.log.debug('apply_postprocessor==False due to ?nopost query arg')
        else:
            self.apply_postprocessor = True
        self.finish_group = frontik.async.AsyncGroup(self.async_callback(self._finish_page_cb),
                                                     name = 'finish',
                                                     log = self.log.debug)
        self._prepared = True

    def require_debug_access(self, login = None, passwd = None):
        if self.debug_access is None:
            if tornado.options.options.debug:
                self.debug_access = True
            else:
                check_login = login if login is not None \
                              else tornado.options.options.debug_login
                check_passwd = passwd if passwd is not None \
                               else tornado.options.options.debug_password

                self.debug_access = frontik.auth.passed_basic_auth(
                    self, check_login, check_passwd)

            if not self.debug_access:
                raise HTTPError(401, headers={'WWW-Authenticate': 'Basic realm="Secure Area"'})

    def finish_with_401(self, auth_header='Basic realm="Secure Area"'):
        #TODO remove this function after cleanup in hh.sites.api - no uses here
        raise HTTPError(401, headers={'WWW-Authenticate': auth_header})


    def get_error_html(self, status_code, **kwargs):
        if  self._prepared and self.debug.debug_mode_logging:
            return self.debug.get_debug_page(status_code, **kwargs)
        else:
            #if not prepared (for example, working handlers count limit) or not in
            #debug mode use default tornado error page
            return super(PageHandler, self).get_error_html(status_code, **kwargs)


    def send_error(self, status_code = 500, headers = None, **kwargs):
        if headers is None:
            headers = {}
        exception = kwargs.get("exception", None)
        need_finish = ((exception is not None) and ((199 < status_code < 400) or
                        (getattr(exception, "xml", None) or getattr(exception, "text", None))))

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

    def finish(self, chunk = None):
        if hasattr(self, 'whc_limit'):
            self.whc_limit.release()

        self.log.debug('done in %.2fms', (time.time() - self.handler_started) * 1000)
        self.log.process_stages()

        # if debug_mode is on: ignore any output we intended to write
        # and use debug log instead
        if hasattr(self, 'debug') and self.debug.debug_mode:
            self.set_header('Content-Type', 'text/html')
            res = self.debug.get_debug_page(self._status_code)
            self._status_code = 200
        else:
            res = chunk

        tornado.web.RequestHandler.finish(self, res)

    def get_page(self):
        ''' Эта функция должна быть переопределена в наследнике и
        выполнять актуальную работу хендлера '''
        raise HTTPError(405)

    def post_page(self):
        ''' Эта функция должна быть переопределена в наследнике и
        выполнять актуальную работу хендлера '''
        raise HTTPError(405)

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

    def fetch_url(self, url, callback = None):
        """
        Прокси метод для get_url, логирующий употребления fetch_url
        """
        from urlparse import parse_qs, urlparse

        self.log.error("Used deprecated method `fetch_url`. %s", traceback.format_stack()[-2][:-1])
        scheme, netloc, path, params, query, fragment = urlparse(url)
        new_url = "{0}://{1}{2}".format(scheme, netloc, path)
        query = parse_qs(query)

        return self.get_url(new_url, data = query, callback = callback)

    def fetch_request(self, req, callback):
        if not self._finished:
            stats.http_reqs_count += 1

            req.headers['X-Request-Id'] = self.request_id
            req.connect_timeout *= tornado.options.options.timeout_multiplier
            req.request_timeout *= tornado.options.options.timeout_multiplier

            return self.http_client.fetch(
                    req,
                    self.finish_group.add(self.async_callback(callback)))
        else:
            self.log.warn('attempted to make http request to %s while page is already finished; ignoring', req.url)

    def get_url(self, url, data = None, headers = None, connect_timeout = 0.5, request_timeout = 2, callback = None, follow_redirects = True, request_types = None):
        placeholder = future.Placeholder()
        request = frontik.util.make_get_request(url,
                                                {} if data is None else data,
                                                {} if headers is None else headers,
                                                connect_timeout,
                                                request_timeout,
                                                follow_redirects)
        self.fetch_request(request, partial(self._fetch_request_response, placeholder, callback, request, request_types = request_types))

        return placeholder

    def get_url_retry(self, url, data = None, headers = None, retry_count = 3, retry_delay = 0.1, connect_timeout = 0.5, request_timeout = 2, callback = None, request_types = None):
        placeholder = future.Placeholder()

        request = frontik.util.make_get_request(url,
                                                {} if data is None else data,
                                                {} if headers is None else headers,
                                                connect_timeout,
                                                request_timeout)

        def step1(retry_count, response):
            if response.error and retry_count > 0:
                self.log.warn('failed to get %s; retries left = %s; retrying', response.effective_url, retry_count)
                # TODO use handler-specific ioloop
                if retry_delay > 0:
                    tornado.ioloop.IOLoop.instance().add_timeout(time.time() + retry_delay,
                        self.finish_group.add(self.async_callback(partial(step2, retry_count))))
                else:
                    step2(retry_count)
            else:
                if response.error and retry_count == 0:
                    self.log.warn('failed to get %s; no more retries left; give up retrying', response.effective_url)

                self._fetch_request_response(placeholder, callback, request, response, request_types = request_types)

        def step2(retry_count):
            self.http_client.fetch(request, self.finish_group.add(self.async_callback(partial(step1, retry_count - 1))))

        self.http_client.fetch(request, self.finish_group.add(self.async_callback(partial(step1, retry_count - 1))))

        return placeholder

    def post_url(self, url, data = '',
                 headers = None,
                 files = None,
                 connect_timeout = 0.5, request_timeout = 2,
                 follow_redirects = True,
                 content_type = None,
                 callback = None,
                 request_types = None):

        placeholder = future.Placeholder()
        request = frontik.util.make_post_request(url,
                                                 data,
                                                 {} if headers is None else headers,
                                                 {} if files is None else files,
                                                 connect_timeout,
                                                 request_timeout,
                                                 follow_redirects,
                                                 content_type)
        self.fetch_request(request, partial(self._fetch_request_response, placeholder, callback, request, request_types = request_types))

        return placeholder

    def put_url(self, url, data='',
                 headers=None,
                 connect_timeout=0.5, request_timeout=2,
                 callback=None,
                 request_types = None):

        placeholder = future.Placeholder()
        request = frontik.util.make_put_request(url,
                                                data,
                                                {} if headers is None else headers,
                                                connect_timeout,
                                                request_timeout)
        self.fetch_request(request, partial(self._fetch_request_response, placeholder, callback, request, request_types=request_types))

        return placeholder

    def delete_url(self, url, data='',
                 headers=None,
                 connect_timeout=0.5, request_timeout=2,
                 callback=None,
                 request_types = None):

        placeholder = future.Placeholder()

        request = frontik.util.make_delete_request(url,
                                                   data,
                                                   {} if headers is None else headers,
                                                   connect_timeout,
                                                   request_timeout)
        self.fetch_request(request,partial(self._fetch_request_response, placeholder, callback, request, request_types=request_types))

        return placeholder

    def _fetch_request_response(self, placeholder, callback, request, response, request_types = None):
        self.log.debug('got %s %s in %.2fms', response.code, response.effective_url, response.request_time * 1000, extra = {"response": response, "request": request})

        if not request_types:
            request_types = default_request_types
        result = None
        if response.error:
            placeholder.set_data(self.show_response_error(response))
        else:
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

            res = None

            if self.text is not None:
                res = self._prepare_finish_plaintext()
            else:
                res = self.xml._finish_xml()

            if hasattr(self.config, 'postprocessor'):
                if self.apply_postprocessor:
                    self.log.debug('applying postprocessor')
                    self.async_callback(self.config.postprocessor)(self, res, self.async_callback(partial(self._wait_postprocessor, time.time())))
                else:
                    self.log.debug('skipping postprocessor')
                    self.finish(res)
            else:
                self.finish(res)

        else:
            self.log.warn('trying to finish already finished page, probably bug in a workflow, ignoring')

    def _wait_postprocessor(self, start_time, data):
        self.log.stage_tag("postprocess")
        self.log.debug("applied postprocessor '%s' in %.2fms",
                self.config.postprocessor,
                (time.time() - start_time) * 1000)
        self.finish(data)

    def _prepare_finish_plaintext(self):
        self.log.debug("finishing plaintext")
        return self.text

    ###

    def xml_from_file(self, filename):
        return self.xml.xml_from_file(filename)

    def set_xsl(self, filename):
        return self.xml.set_xsl(filename)

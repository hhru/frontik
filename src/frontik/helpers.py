# -*- coding: utf-8 -*-

import frontik
import tornado.web
import tornado.httpclient
from frontik.doc import Doc
from functools import wraps, partial

http_client = tornado.httpclient.AsyncHTTPClient()

class Session(object):
    def __init__(self, session_xml):
        self.xml = session_xml

        self.hhid = session_xml.findtext('hhid-session/account/hhid')
        self.email = session_xml.findtext('hhid-session/account/email')
        self.user_id = session_xml.findtext('hh-session/account/user-id')
        self.user_type = session_xml.findtext('hh-session/account/user-type')
        self.lang = session_xml.findtext('locale/lang')
        self.site_id = session_xml.findtext('locale/site-id')
        self.site_code = session_xml.findtext('locale/site-code')
        self.area = session_xml.findtext('locale/area-id')
        platform = session_xml.findtext('locale/platform-code')

        if platform in ['JOBLIST', 'CAREER_RU']:
            self.platform = platform
        else:
            self.platform = 'XHH'

def get_session(func):
    def start_get_session(page):
        hhtoken = page.handler.get_cookie('hhtoken', None)
        hhuid = page.handler.get_cookie('hhuid', None)        
        url = frontik.make_url(page.config.sessionHost + 'hh-session', host = page.handler.request.headers.get("Host"), hhtoken = hhtoken, hhuid = hhuid)
        
        http_client.fetch(url, page.handler.async_callback(partial(get_session_callback, page)))

    def get_session_callback(page, session_response):
        if not session_response.error:
            page.handler.log.debug('got session in %s', session_response.request_time)
            session_xml = frontik.etree.fromstring(session_response.body)
            page.session = Session(session_xml)

        else:
            raise tornado.web.HTTPError(503)  
            page.handler.log.warn('failed to get session: %s', session_response.error)
        print dir(page)
        return func(page)

    return start_get_session

def get_pagedata(func):
    def wrapper(page):
        pagedata = frontik.doc.Doc('pagedata')
        pagedata.put(page.handler.xml_from_file(page.config.pagedata_filename))
        page.doc.put(pagedata)

        if page.session:
            page.doc.put(page.session.xml)
        return func(page)
    return wrapper

def set_xsl(filename):
    def inner_set_xsl(func):
        def wrapped(page):
            page.handler.set_xsl(filename)
            return func(page)
        return wraps(func)(wrapped)
    return inner_set_xsl

class Page(object):
    def __init__(self, handler, config):
        self.handler = handler
        self.config = config
        self.doc = Doc()
        self.session = None

import tornado.web

import tornado.httpclient
http_client = tornado.httpclient.AsyncHTTPClient()

import frontik
from frontik import make_url

import frontik_www.config as config

class Session:
    def __init__(self, session_xml):
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

class SessionPageHandler(frontik.PageHandler):
    @tornado.web.asynchronous
    def get(self):
        self._get_session()
    
    def _get_session(self):
        hhtoken = self.get_cookie('hhtoken', None)
        hhuid = self.get_cookie('hhuid', None)
        
        url = make_url(config.sessionHost + 'hh-session', 
                       host = config.host,
                       hhtoken = hhtoken,
                       hhuid = hhuid)
        
        http_client.fetch(url, self.async_callback(self._get_session_finish))

    def _get_session_finish(self, session_response):
        if not session_response.error:
            self.log.debug('got session in %s', session_response.request_time)
        
            session_xml = frontik.etree.fromstring(session_response.body)
        
            self.session = Session(session_xml)
        
            self.get_page()
        
            self.finish_page()
        else:
            self.log.warn('failed to get session: %s', 
                          session_response.error)
            raise session_response.error

    def get_page(self):
        pass


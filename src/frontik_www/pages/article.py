# -*- coding: utf-8 -*-

import tornado.web

import tornado.httpclient
http_client = tornado.httpclient.AsyncHTTPClient()

import frontik
from frontik import make_url

import frontik_www.config as config
import frontik_www.util
import frontik_www.head
import frontik_www.menu
import frontik_www.foot
import frontik_www.translations

class Session:
    def __init__(self, session_xml):
        self.hhid = session_xml.findtext('hhid-session/account/hhid')
        self.email = session_xml.findtext('hhid-session/account/email')
        self.user_id = session_xml.findtext('hh-session/account/user-id')
        self.user_type = session_xml.findtext('hh-session/account/user-type')
        self.lang = session_xml.findtext('locale/lang')
        self.site_id = session_xml.findtext('locale/site-id')
        self.site_code = session_xml.findtext('locale/site-code')
        self.platform = session_xml.findtext('locale/platform-code')
        self.area = session_xml.findtext('locale/area-id')

class Page(frontik.PageHandler):
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
        self.log.debug('got session in %s', session_response.request_time)
        
        session_xml = frontik.etree.fromstring(session_response.body)
        
        self.session = Session(session_xml)
        
        self.get_page()
        
        self.finish_page()
    
    def get_article(self, article_id):
        if article_id:
            return self.fetch_url(frontik_www.config.planetahrHost + 'xml/article/' + 
                                  str(article_id) + '/' + self.session.site_code + '/' + self.session.lang)

    def get_page(self):
        # TODO response.set_xsl('article.xsl')
        
        self.doc.put(self.get_article(599))
        self.doc.put(self.get_article(self.get_argument('articleId')))
        
        banners = frontik_www.util.Banners(self)
        self.doc.put(banners.get_banners([137, 138, 144]))

        frontik_www.head.do_head(self)
        
        frontik_www.menu.do_menu(self)
        
        frontik_www.foot.do_foot(self)
        
        self.doc.put(frontik_www.translations.get_translations(self, frontik_www.translations.index_translations))

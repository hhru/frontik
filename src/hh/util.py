# -*- coding: utf-8 -*-

import time
import random

import frontik
#from frontik.http_client import http_get

import config

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

def get_session(request):
    hhtoken = request.cookies.get('hhtoken')
    hhuid = request.cookies.get('hhuid')
    
    url = frontik.make_url(config.sessionHost + 'hh-session', 
                   host = config.host,
                   hhtoken = hhtoken, 
                   hhuid = hhuid)

    session_xml = frontik.http_get(url).get()
    
    return Session(session_xml)

class Banners(object):
    def __init__(self, request, response, session):
        self.request = request
        self.response = response
        self.session = session
        
        self._init_user_cookie()
        self._init_banners_uri()
        
    def _init_user_cookie(self):
        cookie = self.request.cookies.get('unique_banner_user')
        
        if cookie:
            self.unique_banner_user = cookie
        
        else:
            cookie = '%s%s' % (time.time(), random.randint(0,10000000000000))
            self.response.response.set_cookie('unique_banner_user', cookie,
                                              path='/',
                                              max_age=60*60*24)
            
            self.unique_banner_user = cookie
        
    def _init_banners_uri(self):
        if self.request.params.get('professionalAreaId', '') and self.request.params.get('professionalAreaId', '') <> '0':
            specializationListRequestConcat = '&specializationId='.join(self.request.params.getall('specializationId'))
    
            if specializationListRequestConcat == '':
                specializationListForBanner = '' # TODO return
            else:
                specializationListForBanner = '&specializationId=' + specializationListRequestConcat
        else:
            specializationListForBanner = ''
    
        self.uriBanner = frontik.make_url(config.serviceHost + 'bannerList',
                                  uuid=self.unique_banner_user,
                                  userId=self.session.user_id,
                                  siteId=self.session.site_id,
                                  professionalAreaId=self.request.params.get('professionalAreaId'),
                                  areaId=self.request.params.get('areaId')) + specializationListForBanner
        
        self.uriBannerMulti = self.uriBanner + '&multy=true'
    
    def get_banners(self, place_ids):
        return frontik.http_get(self.uriBanner + ''.join('&placeId=%s' % (i,) for i in place_ids))


# -*- coding: utf-8 -*-

import urllib
import time
import random

from frontik.http_client import http_get

import config

def make_url(base, **query_args):
    ''' 
    построить URL из базового урла и набора CGI-параметров
    параметры с пустым значением пропускаются, удобно для последовательности:
    make_url(base, hhtoken=request.cookies.get('hhtoken'))
    '''
    
    qs = urllib.urlencode([(key, val) 
                           for (key,val) in query_args.iteritems()
                           if val])
    
    if qs:
        return base + '?' + qs
    else:
        return base 

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
    
    url = make_url(config.sessionHost + 'hh-session', 
                   host = config.host,
                   hhtoken = hhtoken, 
                   hhuid = hhuid)

    session_xml = http_get(url).get()
    
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
    
        if self.request.params.get('areadId'):
            bannerArea = '&areaId=' + self.request.params.get('areadId')
        else:
            bannerArea = ''
        
        self.uriBanner = make_url(config.serviceHost + 'bannerList',
                                  uuid=self.unique_banner_user,
                                  userId=self.session.user_id,
                                  siteId=self.session.site_id,
                                  professionalAreaId=self.request.params.get('professionalAreaId'),
                                  areaId=self.request.params.get('areaId')) + specializationListForBanner
        
        self.uriBannerMulti = self.uriBanner + '&multy=true'
    
    def get_banners(self, place_ids):
        return http_get(self.uriBanner + ''.join('&placeId=%s' % (i,) for i in place_ids))


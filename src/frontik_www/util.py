# -*- coding: utf-8 -*-

import time
import random

import frontik
#from frontik.http_client import http_get

import config

class Banners(object):
    def __init__(self, handler):
        self.handler = handler
        
        self._init_user_cookie()
        self._init_banners_uri()
        
    def _init_user_cookie(self):
        cookie = self.handler.get_cookie('unique_banner_user', '')
        
        if cookie:
            self.unique_banner_user = cookie
        
        else:
            cookie = '%s%s' % (time.time(), random.randint(0,10000000000000))
            self.handler.set_cookie('unique_banner_user', cookie, expires_days=1)
            
            self.unique_banner_user = cookie
        
    def _init_banners_uri(self):
        if self.handler.get_argument('professionalAreaId', '') and self.handler.get_argument('professionalAreaId', '') <> '0':
            specializationListRequestConcat = '&specializationId='.join(self.handler.request.arguments.get('specializationId'))
    
            if specializationListRequestConcat == '':
                specializationListForBanner = '' # TODO return
            else:
                specializationListForBanner = '&specializationId=' + specializationListRequestConcat
        else:
            specializationListForBanner = ''
    
        self.uriBanner = frontik.make_url(config.serviceHost + 'bannerList',
                                  uuid=self.unique_banner_user,
                                  userId=self.handler.session.user_id,
                                  siteId=self.handler.session.site_id,
                                  professionalAreaId=self.handler.get_argument('professionalAreaId', ''),
                                  areaId=self.handler.get_argument('areaId', '')) + specializationListForBanner
        
        self.uriBannerMulti = self.uriBanner + '&multy=true'
    
    def get_banners(self, place_ids):
        return self.handler.fetch_url(self.uriBanner + ''.join('&placeId=%s' % (i,) for i in place_ids))


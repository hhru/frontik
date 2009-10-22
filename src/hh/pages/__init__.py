# -*- coding: utf-8 -*-

import time
import random

from frontik import DocResponse
from frontik.http_client import http_get

import config
import util

def get_article(session, article_id):
    return http_get(config.planetahrHost + 'xml/article/' + 
                    str(article_id) + '/' + session.site_code + '/' + session.lang)

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
            cookie = '%s%s' % (time.time(), random.randint(10000000000000))
            self.response.set_cookie('unique_banner_user', cookie,
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
        
        self.uriBanner = (config.serviceHost +
                          'bannerList?' + 
                          'uuid=' + self.unique_banner_user +
                          '&userId=' + self.session.user_id +
                          '&siteId=' + self.session.site_id + 
                          '&professionalAreaId=' + self.request.params.get('professionalAreaId', '') +
                          specializationListForBanner +
                          bannerArea)
        
        self.uriBannerMulti = self.uriBanner + '&multy=true'
    
    def get_banners(self, place_ids):
        return http_get(self.uriBanner + ''.join('&placeId=%s' % (i,) for i in place_ids))

def article(request):
#  <xi:include href="xml/page.xml"/>

    response = DocResponse('article')
    # TODO response.set_xsl('article.xsl')

    session = util.get_session(request)
        
    response.doc.put(get_article(session, 599))
    response.doc.put(get_article(session, request.GET['articleId']))
    
    banners = Banners(request, response, session)
    
    response.doc.put(banners.get_banners([137, 138, 144]))

#  <xi:include href="xml/head/full.xml"/>
#  <xi:include href="xml/data/menu.xml"/>
#  <xi:include href="xml/foot.xml"/>
#  <xi:include href="xml/translations/index.xml"/>

    return response

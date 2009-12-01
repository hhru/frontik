# -*- coding: utf-8 -*-

import time
import random

import frontik
from frontik import make_url

import config

def init_user_cookie(handler):
    cookie = handler.get_cookie('unique_banner_user', '')

    if cookie:
        unique_banner_user = cookie

    else:
        cookie = '%s%s' % (time.time(), random.randint(0,10000000000000))
        handler.set_cookie('unique_banner_user', cookie, expires_days=1)

        unique_banner_user = cookie

    return unique_banner_user

class Banners:
    def __init__(self, handler):
        self.handler = handler
        self.unique_banner_user = init_user_cookie(handler)

        if self.handler.get_argument('professionalAreaId', '') \
                and self.handler.get_argument('professionalAreaId', '') <> '0':
            self.specialization_list = self.handler.request.arguments.get('specializationId')
        else:
            self.specialization_list = []
    
    def get_banners_url(self, place_ids):
        uri_banner = make_url(config.serviceHost + 'bannerList',

                              uuid = self.unique_banner_user,
                              userId = self.handler.session.user_id,
                              siteId = self.handler.session.site_id,
                              professionalAreaId = self.handler.get_argument('professionalAreaId', ''),
                              areaId = self.handler.get_argument('areaId', ''), 
                              specializationId = self.specialization_list,
                              placeId = place_ids)

        return uri_banner


def do_banners(handler, specific_place_ids):
    b = Banners(handler)

    if handler.session.platform == 'XHH':
        base_place_ids = [9, 11, 15]

    elif handler.session.platform == 'JOBLIST':
        base_place_ids = [1, 137, 138, 139, 144, 148]

    else:
        base_place_ids = []

    handler.doc.put(handler.fetch_url(b.get_banners_url(base_place_ids + specific_place_ids)))
